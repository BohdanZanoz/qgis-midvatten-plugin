# -*- coding: utf-8 -*-
"""
/***************************************************************************
 This part of the Midvatten plugin handles importing of data to the database
  from the fieldlogger format.

 This part is to a big extent based on QSpatialite plugin.
                             -------------------
        begin                : 2016-11-27
        copyright            : (C) 2016 by HenrikSpa (and joskal)
        email                : groundwatergis [at] gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import range
from builtins import object

import copy
import io
import os
from queue import Queue
from collections import OrderedDict
from datetime import datetime
from functools import partial
from time import sleep


import qgis.PyQt
from qgis.PyQt.QtCore import QCoreApplication

import definitions.midvatten_defs
import import_data_to_db
import db_utils
import midvatten_utils as utils
from midvatten_utils import returnunicode as ru
from date_utils import datestring_to_date, dateshift
from definitions import midvatten_defs as defs
from gui_utils import SplitterWithHandel, RowEntry, RowEntryGrid
from gui_utils import DateTimeFilter


import_fieldlogger_ui_dialog =  qgis.PyQt.uic.loadUiType(os.path.join(os.path.dirname(__file__),'..','ui', 'import_fieldlogger.ui'))[0]

class FieldloggerImport(qgis.PyQt.QtWidgets.QMainWindow, import_fieldlogger_ui_dialog):
    def __init__(self, parent, msettings=None):
        self.status = False
        self.iface = parent
        self.ms = msettings
        self.ms.loadSettings()
        qgis.PyQt.QtWidgets.QDialog.__init__(self, parent)
        self.setAttribute(qgis.PyQt.QtCore.Qt.WA_DeleteOnClose)
        self.setupUi(self)  # Required by Qt4 to initialize the UI
        self.status = True

    def parse_observations_and_populate_gui(self):
        splitter = SplitterWithHandel(qgis.PyQt.QtCore.Qt.Vertical)
        self.add_row(splitter)

        self.observations = self.select_file_and_parse_rows(self.parse_rows)
        if self.observations is None:
            return None

        #Filters and general settings
        settings_widget = qgis.PyQt.QtWidgets.QWidget()
        settings_layout = qgis.PyQt.QtWidgets.QVBoxLayout()
        settings_widget.setLayout(settings_layout)
        splitter.addWidget(settings_widget)
        self.settings = []
        self.settings.append(StaffQuestion())
        self.settings.append(DateShiftQuestion())
        self.date_time_filter = DateTimeFilter(stretch=False)
        self.date_time_filter.date_time_filter_update_button = qgis.PyQt.QtWidgets.QPushButton(QCoreApplication.translate('FieldloggerImport',
                                                                                                 'Filter dates'))
        self.date_time_filter.date_time_filter_update_button.setToolTip(ru(QCoreApplication.translate('FieldloggerImport',
                                                                                     'Filter observations using from and to dates and update gui.')))
        self.date_time_filter.layout.addWidget(self.date_time_filter.date_time_filter_update_button)
        self.date_time_filter.layout.addStretch()

        self.settings.append(self.date_time_filter)
        for setting in self.settings:
            if hasattr(setting, 'widget'):
                settings_layout.addWidget(setting.widget)
        #self.add_line(settings_layout)

        #Settings with own loop gets self.observations to work on.
        self.settings_with_own_loop = [ObsidFilter()]

        #Sublocations
        sublocations = [observation['sublocation'] for observation in self.observations]
        sublocations_widget = qgis.PyQt.QtWidgets.QWidget()
        sublocations_layout = qgis.PyQt.QtWidgets.QVBoxLayout()
        sublocations_widget.setLayout(sublocations_layout)
        sublocations_layout.addWidget(qgis.PyQt.QtWidgets.QLabel(ru(QCoreApplication.translate('FieldloggerImport', 'Select sublocations to import:'))))
        splitter.addWidget(sublocations_widget)
        self.sublocation_filter = SublocationFilter(sublocations)
        self.settings.append(self.sublocation_filter)
        sublocations_layout.addWidget(self.settings[-1].widget)
        #self.add_line(sublocations_layout)

        self.stored_settingskey = 'fieldlogger_import_parameter_settings'
        self.stored_settings = utils.get_stored_settings(self.ms, self.stored_settingskey)

        #Input fields
        self.input_fields = InputFields()
        self.input_fields.update_parameter_imports_queue(self.observations, self.stored_settings)

        splitter.addWidget(self.input_fields.widget)

        #General buttons
        self.save_settings_button = qgis.PyQt.QtWidgets.QPushButton(ru(QCoreApplication.translate('FieldloggerImport', 'Save settings')))
        self.gridLayout_buttons.addWidget(self.save_settings_button, 0, 0)
        self.save_settings_button.clicked.connect(
                         lambda : [x() for x in [lambda : self.input_fields.update_stored_settings(self.stored_settings),
                                       lambda : utils.save_stored_settings(self.ms, self.stored_settings, self.stored_settingskey)]])

        self.clear_settings_button = qgis.PyQt.QtWidgets.QPushButton(ru(QCoreApplication.translate('FieldloggerImport', 'Clear settings')))
        self.clear_settings_button.setToolTip(ru(QCoreApplication.translate('FieldloggerImport', 'Clear all parameter settings\nReopen Fieldlogger import gui to have it reset,\nor press "Save settings" to undo.')))
        self.gridLayout_buttons.addWidget(self.clear_settings_button, 1, 0)
        self.clear_settings_button.clicked.connect(
                     lambda: [x() for x in [lambda: utils.save_stored_settings(self.ms, [], self.stored_settingskey),
                                  lambda: utils.pop_up_info(ru(QCoreApplication.translate('FieldloggerImport', 'Settings cleared. Restart import Fieldlogger dialog')))]])

        self.close_after_import = qgis.PyQt.QtWidgets.QCheckBox(ru(QCoreApplication.translate('FieldloggerImport', 'Close dialog after import')))
        self.close_after_import.setChecked(True)
        self.gridLayout_buttons.addWidget(self.close_after_import, 2, 0)

        self.start_import_button = qgis.PyQt.QtWidgets.QPushButton(ru(QCoreApplication.translate('FieldloggerImport', 'Start import')))
        self.gridLayout_buttons.addWidget(self.start_import_button, 3, 0)
        self.start_import_button.clicked.connect(lambda : self.start_import(self.observations))

        self.date_time_filter.date_time_filter_update_button.clicked.connect(
                     self.update_sublocations_and_inputfields_on_date_change)

        #Button click first filters data from the settings and then updates input fields.
        self.input_fields.update_parameters_button.clicked.connect(
                     self.update_input_fields_from_button)

        self.gridLayout_buttons.setRowStretch(4, 1)

        self.setGeometry(500, 150, 950, 700)

        self.show()

    @staticmethod
    @utils.general_exception_handler
    def select_file_and_parse_rows(row_parser):
        filenames = utils.select_files(only_one_file=False, extension="csv (*.csv)")
        print(str(filenames))
        if filenames is None or not filenames:
            raise utils.UserInterruptError()
        observations = []
        for filename in filenames:
            filename = ru(filename)
            print(str(filename))
            supported_encodings = ['utf-8', 'cp1252']
            for encoding in supported_encodings:
                try:
                    delimiter = utils.get_delimiter(filename=filename, charset=encoding, delimiters=[';', ','], num_fields=5)
                    if delimiter is None:
                        return None

                    with io.open(filename, 'rt', encoding=encoding) as f:
                        #Skip header
                        f.readline()
                        observations.extend(row_parser(f, delimiter))

                except UnicodeDecodeError:
                    continue
                else:
                    break

        #Remove duplicates
        observations = [dict(no_duplicate) for no_duplicate in set([tuple(possible_duplicate.items()) for possible_duplicate in observations])]

        return observations

    @staticmethod
    def parse_rows(f, delimiter=';'):
        """
        Parses rows from fieldlogger format into a dict
        :param f: File_data, often an open file or a list of rows without header
        :return: a list of dicts like [{date_time: x, sublocation: y, parametername: z, value: o}, ...]

        """
        observations = []
        for rownr, rawrow in enumerate(f):
            observation = {}
            row = ru(rawrow).rstrip('\r').rstrip('\n')
            if not row:
                continue
            cols = row.split(delimiter)
            observation['sublocation'] = cols[0]
            date = cols[1]
            time = cols[2]
            observation['date_time'] = datestring_to_date(' '.join([date, time]))
            observation['value'] = cols[3]
            observation['parametername'] = cols[4]
            if observation['value']:
                observations.append(observation)
        return observations

    def add_row(self, a_widget):
        """
        :param: a_widget:
        """
        self.main_vertical_layout.addWidget(a_widget)

    def add_line(self, layout=None):
        """ just adds a line"""
        #horizontalLineWidget = PyQt4.QtWidgets.QWidget()
        #horizontalLineWidget.setFixedHeight(2)
        #horizontalLineWidget.setSizePolicy(PyQt4.QtWidgets.QSizePolicy.Expanding, PyQt4.QtWidgets.QSizePolicy.Fixed)
        #horizontalLineWidget.setStyleSheet(PyQt4.QtCore.QString("background-color: #c0c0c0;"));
        line = qgis.PyQt.QtWidgets.QFrame()
        #line.setObjectName(QString::fromUtf8("line"));
        line.setGeometry(qgis.PyQt.QtCore.QRect(320, 150, 118, 3))
        line.setFrameShape(qgis.PyQt.QtWidgets.QFrame.HLine);
        line.setFrameShadow(qgis.PyQt.QtWidgets.QFrame.Sunken);
        if layout is None:
            self.add_row(line)
        else:
            layout.addWidget(line)

    @staticmethod
    def sublocation_to_groups(sublocations, delimiter='.'):
        """
        This method splits sublocation using a splitter, default to u'.'. Each list position is grouped to lists
         containing all distinct values. It's finally stored in a dict with the lenght of the splitted group as key.
        :param: sublocations: A list of sublocations, ex: ['c', 'a.1', 'a.2', 'b.1.1']
        :return: a dict like {1: [set(distinct values)], 2: [set(distinct values)}, set(), set()], ...)
        """
        sublocation_groups = {}
        for sublocation in sublocations:
            splitted = sublocation.split(delimiter)
            length = len(splitted)
            for index in range(length):
                #a dict like {1: [set()], 2: [set(), set()], ...}
                sublocation_groups.setdefault(length, [set()for i in range(length)])[index].add(splitted[index])
        return sublocation_groups

    def update_sublocations_and_inputfields_on_date_change(self):
        sleep(0.2)
        observations = copy.deepcopy(self.observations)
        date_time_filter = self.date_time_filter
        sublocation_filter = self.sublocation_filter
        input_fields = self.input_fields
        stored_settings = self.stored_settings

        observations = copy.deepcopy(observations)
        observations = self.filter_by_settings_using_shared_loop(observations, [date_time_filter])
        sublocations = [observation['sublocation'] for observation in observations]
        sublocation_filter.update_sublocations(sublocations)
        observations = self.filter_by_settings_using_shared_loop(observations, [sublocation_filter])
        input_fields.update_parameter_imports_queue(observations, stored_settings)

    @utils.general_exception_handler
    def update_input_fields_from_button(self):
        self.input_fields.update_parameter_imports_queue(self.filter_by_settings_using_shared_loop(self.observations, self.settings), self.stored_settings)

    @staticmethod
    def prepare_w_levels_data(observations):
        """
        Produces a filestring with columns "obsid, date_time, meas, comment" and imports it
        :param obsdict: a dict like {obsid: {date_time: {parameter: value}}}
        :return: None
        """
        file_data_list = [['obsid', 'date_time', 'meas', 'h_toc', 'level_masl', 'comment']]
        for observation in observations:
            obsid = observation['obsid']
            date_time = datetime.strftime(observation['date_time'], '%Y-%m-%d %H:%M:%S')
            level_masl = observation.get('level_masl', '').replace(',', '.')
            h_toc = observation.get('h_toc', '').replace(',', '.')
            meas = observation.get('meas', '').replace(',', '.')
            comment = observation.get('comment', '')

            file_data_list.append([obsid, date_time, meas, h_toc, level_masl, comment])

        return file_data_list

    @staticmethod
    def prepare_comments_data(observations):
        file_data_list = [['obsid', 'date_time', 'comment', 'staff']]
        for observation in observations:

            if observation.get('skip_comment_import', False):
                continue
            obsid = observation['obsid']
            date_time = datetime.strftime(observation['date_time'], '%Y-%m-%d %H:%M:%S')
            comment = observation['value']
            staff = observation['staff']
            file_data_list.append([obsid, date_time, comment, staff])
        return file_data_list

    @staticmethod
    def prepare_w_flow_data(observations):
        """
        Produces a filestring with columns "obsid, instrumentid, flowtype, date_time, reading, unit, comment" and imports it
        :param obsdict:  a dict like {obsid: {date_time: {parameter: value}}}
        :return:
        """

        file_data_list = [['obsid', 'instrumentid', 'flowtype', 'date_time', 'reading', 'unit', 'comment']]
        instrumentids = utils.get_last_used_flow_instruments()[1]
        already_asked_instruments = {}

        for observation in observations:
            obsid = observation['obsid']
            flowtype = observation['flowtype']
            date_time = datetime.strftime(observation['date_time'], '%Y-%m-%d %H:%M:%S')
            unit = observation['unit']
            sublocation = observation['sublocation']

            instrumentid = already_asked_instruments.get(sublocation, None)
            if instrumentid is None:
                instrumentids_for_obsid = instrumentids.get(obsid, None)
                if instrumentids_for_obsid is None:
                    last_used_instrumentid = ['']
                else:
                    last_used_instrumentid = sorted(
                        [(_date_time, _instrumentid) for _flowtype, _instrumentid, _date_time in instrumentids[obsid] if
                         (_flowtype == flowtype)], reverse=True)
                    if last_used_instrumentid:
                        last_used_instrumentid = [x[1] for x in last_used_instrumentid]
                    else:
                        last_used_instrumentid = ['']
                question = utils.NotFoundQuestion(dialogtitle=ru(QCoreApplication.translate('FieldloggerImport', 'Submit instrument id')),
                                                  msg=''.join([ru(QCoreApplication.translate('FieldloggerImport', 'Submit the instrument id for the measurement:\n ')),
                                                                ', '.join([sublocation, obsid, date_time, flowtype, unit])]),
                                                  existing_list=last_used_instrumentid,
                                                  default_value=last_used_instrumentid[0],
                                                  combobox_label=ru(QCoreApplication.translate('FieldloggerImport', 'Instrument id:s in database for obsid %s.\nThe last used instrument id for obsid %s is prefilled:'))%(obsid, obsid))
                answer = question.answer
                if answer == 'cancel':
                    raise utils.UserInterruptError()
                instrumentid = ru(question.value)
                already_asked_instruments[sublocation] = instrumentid

            reading = observation['value'].replace(',', '.')

            comment = observation.get('comment', '')
            file_data_list.append([obsid, instrumentid, flowtype, date_time, reading, unit, comment])

        return file_data_list

    @staticmethod
    def prepare_w_qual_field_data(observations):
        """
        Produces a filestring with columns "obsid, staff, date_time, instrument, parameter, reading_num, reading_txt, unit, depth, comment" and imports it
        :param obsdict:  a dict like {obsid: {date_time: {parameter: value}}}
        :param quality_or_water_sample: Word written at user question: 'quality' or 'water sample'.
        :return:
        """
        file_data_list = [['obsid', 'staff', 'date_time', 'instrument', 'parameter', 'reading_num', 'reading_txt', 'unit', 'depth', 'comment']]

        for observation in observations:
            obsid = observation['obsid']
            staff = observation['staff']
            date_time = datetime.strftime(observation['date_time'], '%Y-%m-%d %H:%M:%S')
            instrument = observation['instrument']
            parameter = observation['parameter']
            reading_num = observation['value'].replace(',', '.')
            reading_txt = observation['value']
            unit = observation['unit']
            depth = observation.get('depth', '').replace(',', '.')
            comment = observation.get('comment', '')
            file_data_list.append([obsid, staff, date_time, instrument, parameter, reading_num, reading_txt, unit, depth, comment])

        return file_data_list

    @staticmethod
    def filter_by_settings_using_shared_loop(observations, settings):

        observations = copy.deepcopy(observations)
        filtered_observations = []
        for observation in observations:
            for setting in settings:
                observation = setting.alter_data(observation)
                if observation is None:
                    break
            if observation is not None:
                filtered_observations.append(observation)
        observations = filtered_observations
        return observations

    @staticmethod
    def filter_by_settings_using_own_loop(observations, settings_with_own_loop):

        observations = copy.deepcopy(observations)
        for setting in settings_with_own_loop:
            observations = setting.alter_data(observations)
        return observations

    @utils.general_exception_handler
    @import_data_to_db.import_exception_handler
    def start_import(self, observations):
        """

        :param observations:
        :return:
        """
        observations = copy.deepcopy(observations)

        #Start by saving the parameter settings
        self.input_fields.update_stored_settings(self.stored_settings)
        utils.save_stored_settings(self.ms, self.stored_settings, self.stored_settingskey)

        chosen_methods = [import_method_chooser.import_method for import_method_chooser in list(self.input_fields.parameter_imports.values())
                          if import_method_chooser.import_method]
        if not chosen_methods:
            utils.pop_up_info(ru(QCoreApplication.translate('FieldloggerImport', "Must choose at least one parameter import method")))
            utils.MessagebarAndLog.critical(bar_msg=ru(QCoreApplication.translate('FieldloggerImport', "No parameter import method chosen")))
            return None

        #Update the observations using the general settings, filters and parameter settings
        observations = self.input_fields.filter_import_methods_not_set(observations)
        observations = self.filter_by_settings_using_shared_loop(observations, self.settings)
        observations = self.filter_by_settings_using_own_loop(observations, self.settings_with_own_loop)
        observations = self.input_fields.update_observations(observations)

        if not observations:
            utils.MessagebarAndLog.warning(bar_msg=ru(QCoreApplication.translate('FieldloggerImport', "No observations left to import after filtering")))
            return None

        observations_importmethods = self.input_fields.get_observations_importmethods(observations)

        importer = import_data_to_db.midv_data_importer()

        data_preparers = {'w_levels': self.prepare_w_levels_data,
                          'w_flow': self.prepare_w_flow_data,
                          'w_qual_field': self.prepare_w_qual_field_data,
                          'comments': self.prepare_comments_data,
                          'w_qual_field_depth': lambda x: None}

        for import_method, observations in observations_importmethods.items():
            if import_method:
                file_data = data_preparers[import_method](observations)
                if file_data is None:
                    continue

                importer.general_import(file_data=file_data, goal_table=import_method)

        importer.SanityCheckVacuumDB()

        if self.close_after_import.isChecked():
            self.close()
        qgis.PyQt.QtWidgets.QApplication.restoreOverrideCursor()


class ObsidFilter(object):
    def __init__(self):
        self.obsid_rename_dict = {}
        pass

    def alter_data(self, observations):
        observations = copy.deepcopy(observations)
        existing_obsids = utils.get_all_obsids()

        for observation in observations:
            observation['obsid'] = observation['sublocation'].split('.')[0]

        obsids = [list(x) for x in sorted(set([(observation['obsid'], observation['obsid']) for observation in observations if observation['obsid'] not in self.obsid_rename_dict]))]
        if obsids:
            obsids.reverse()
            obsids.append(['old_obsid', 'new_obsid'])
            obsids.reverse()

            answer = utils.filter_nonexisting_values_and_ask(obsids, 'new_obsid', existing_values=existing_obsids, try_capitalize=False)

            if answer is not None:
                if isinstance(answer, (list, tuple)):
                    if len(answer) > 1:
                        self.obsid_rename_dict.update(dict([(old_obsid_new_obsid[0], old_obsid_new_obsid[1]) for old_obsid_new_obsid in answer[1:]]))

        #Filter and rename obsids
        if self.obsid_rename_dict:
            [observation.update({'obsid': self.obsid_rename_dict.get(observation['obsid'], None)})
                for observation in observations]
            observations = [observation for observation in observations if all([observation['obsid'] is not None, observation['obsid']])]

        if len(observations) == 0:
            raise utils.UsageError(ru(QCoreApplication.translate('ObsidFilter', 'No observations returned from obsid verification. Were all skipped?')))
        return observations


class StaffQuestion(RowEntry):
    def __init__(self):
        super(StaffQuestion, self).__init__()
        self.label = qgis.PyQt.QtWidgets.QLabel(ru(QCoreApplication.translate('StaffQuestion', 'Staff who did the measurement')))
        self.existing_staff_combobox = default_combobox()
        existing_staff = sorted(defs.staff_list()[1])
        self.existing_staff_combobox.addItems(existing_staff)

        for widget in [self.label, self.existing_staff_combobox]:
            self.layout.addWidget(widget)
        self.layout.addStretch()

    @property
    def staff(self):
        return ru(self.existing_staff_combobox.currentText())

    @staff.setter
    def staff(self, value):
        self.existing_staff_combobox.setEditText(value)

    def alter_data(self, observation):
        observation = copy.deepcopy(observation)
        if self.staff is None or not self.staff:
            raise utils.UsageError(ru(QCoreApplication.translate('StaffQuestion', 'Import error, staff not given')))

        observation['staff'] = self.staff
        return observation


class DateShiftQuestion(RowEntry):
    def __init__(self):
        super(DateShiftQuestion, self).__init__()
        self.label = qgis.PyQt.QtWidgets.QLabel(ru(QCoreApplication.translate('DateShiftQuestion', 'Shift dates, supported format ex. "%s":'))%'-1 hours')
        self.dateshift_lineedit = qgis.PyQt.QtWidgets.QLineEdit()
        self.dateshift_lineedit.setText('0 hours')

        for widget in [self.label, self.dateshift_lineedit]:
            self.layout.addWidget(widget)
        self.layout.insertStretch(-1, 1)

    def alter_data(self, observation):
        observation = copy.deepcopy(observation)
        shift_specification = ru(self.dateshift_lineedit.text())

        step_steplength = shift_specification.split(' ')
        failed = False

        bar_msg = ru(QCoreApplication.translate('DateShiftQuestion', 'Dateshift specification wrong format, se log message panel'))

        log_msg = (ru(QCoreApplication.translate('DateShiftQuestion', 'Dateshift specification must be made using format "step step_length", ex: "%s", "%s", "%s" etc.\nSupported step lengths: %s'))%('0 hours', '-1 hours', '-1 days', 'microseconds, milliseconds, seconds, minutes, hours, days, weeks.'))

        if len(step_steplength) != 2:
            utils.MessagebarAndLog.warning(bar_msg=bar_msg, log_msg=log_msg)
            raise utils.UsageError()
        try:
            step = float(step_steplength[0])
            steplength = step_steplength[1]
        except:
            utils.MessagebarAndLog.warning(bar_msg=bar_msg, log_msg=log_msg)
            raise utils.UsageError()

        test_shift = dateshift('2015-02-01', step, steplength)
        if test_shift == None:
            utils.MessagebarAndLog.warning(bar_msg=bar_msg, log_msg=log_msg)
            raise utils.UsageError()

        observation['date_time'] = dateshift(observation['date_time'], step, steplength)

        return observation


class SublocationFilter(RowEntry):
    def __init__(self, sublocations):
        """

        :param sublocations: a list like ['a.b', '1.2.3', ...]
        """
        super(SublocationFilter, self).__init__()
        self.table = qgis.PyQt.QtWidgets.QTableWidget()
        self.table.setSelectionBehavior(qgis.PyQt.QtWidgets.QAbstractItemView.SelectRows)
        self.table.sizePolicy().setVerticalPolicy(qgis.PyQt.QtWidgets.QSizePolicy.MinimumExpanding)
        self.table.sizePolicy().setVerticalStretch(2)
        self.table.setSelectionMode(qgis.PyQt.QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)

        self.update_sublocations(sublocations)

        self.layout.addWidget(self.table)
        self.layout.addStretch()

    def set_selection(self, sublocations, true_or_false):
        """

        :param sublocations: an iterable, ex: list, tuple etc. of sublocation strings
        :param true_or_false: True/False. Sets selection to this
        :return:
        """
        for sublocation in sublocations:
            self.table.setItemSelected(self.table_items[sublocation], true_or_false)

    def alter_data(self, observation):
        observation = copy.deepcopy(observation)
        sublocation = observation['sublocation']

        if self.table_items[sublocation].isSelected():
            return observation
        else:
            return None

    def update_sublocations(self, sublocations):
        self.table.clear()

        sublocations = sorted(list(set(sublocations)))

        if not sublocations:
            num_rows = 1
            num_columns = 1
        else:
            num_rows = len(sublocations)
            #num_columns = reduce(lambda x, y: max(x , len(y.split('.'))), sublocations, 0)
            num_columns = max([len(sublocation.split('.')) for sublocation in sublocations])

        self.table.setRowCount(num_rows)
        self.table.setColumnCount(num_columns)

        self.table_items = {}
        for rownr, sublocation in enumerate(sublocations):
            for colnr, value in enumerate(sublocation.split('.')):
                tablewidgetitem = qgis.PyQt.QtWidgets.QTableWidgetItem(value)
                if sublocation not in self.table_items:
                    self.table_items[sublocation] = tablewidgetitem
                self.table.setItem(rownr, colnr, tablewidgetitem)

        self.table.resizeColumnsToContents()

        self.table.selectAll()


class InputFields(RowEntry):
    def __init__(self):
        self.widget = qgis.PyQt.QtWidgets.QWidget()
        self.layout = qgis.PyQt.QtWidgets.QVBoxLayout()
        self.widget.setLayout(self.layout)


        self.all_children = []

        self.active_updater = False
        self.update_queue = Queue()
        self.update_queue_working = False

        self.layout.addWidget(qgis.PyQt.QtWidgets.QLabel(ru(QCoreApplication.translate('InputFields', 'Specify import methods for input fields'))))

        self.parameter_imports = OrderedDict()

        #This button has to get filtered observations as input, so it has to be
        #connected elsewhere.
        self.update_parameters_button = qgis.PyQt.QtWidgets.QPushButton(ru(QCoreApplication.translate('InputFields', 'Update input fields')))
        self.update_parameters_button.setToolTip(ru(QCoreApplication.translate('InputFields', 'Update input fields using the observations remaining after filtering by date and sublocation selection.')))
        self.layout.addWidget(self.update_parameters_button)

    def update_parameter_imports_queue(self, *args, **kwargs):
        if self.update_queue_working:
            self.update_queue.put(partial(self.update_parameter_imports, *args, **kwargs))
            return
        else:
            self.update_queue_working = True
            self.update_queue.put(partial(self.update_parameter_imports, *args, **kwargs))
            while not self.update_queue.empty():
                upd_func = self.update_queue.get()
                upd_func()
                self.update_queue.task_done()
            else:
                self.update_queue_working = False


    def update_parameter_imports(self, observations, stored_settings=None):

        if stored_settings is None:
            stored_settings = []

        #Remove and close all widgets
        while self.parameter_imports:
            try:
                k, imp_obj = self.parameter_imports.popitem()
            except KeyError:
                break
            self.layout.removeWidget(imp_obj.widget)
            imp_obj.close()

        for child in self.all_children:
            child.close()

        observations = copy.deepcopy(observations)
        parameter_names = list(set([observation['parametername'] for observation in observations]))

        maximumwidth = 0
        for parametername in parameter_names:
            testlabel = qgis.PyQt.QtWidgets.QLabel()
            testlabel.setText(parametername)
            maximumwidth = max(maximumwidth, testlabel.sizeHint().width())
        testlabel = None

        if self.parameter_imports:
            return

        for parametername in parameter_names:
            param_import_obj = ImportMethodChooser(parametername, parameter_names)
            param_import_obj.label.setFixedWidth(maximumwidth)
            if parametername not in self.parameter_imports:
                self.parameter_imports[parametername] = param_import_obj
                self.layout.addWidget(param_import_obj.widget)
                if param_import_obj.widget not in self.all_children:
                    self.all_children.append(param_import_obj.widget)

        self.set_parameters_using_stored_settings(stored_settings)

        #utils.MessagebarAndLog.info(log_msg="Imports in self.parameter_imports:\n" + '\n'.join([': '.join([k, str(v), v.parameter_name, str(v.widget)]) for k, v in self.parameter_imports.iteritems()]))
        #utils.MessagebarAndLog.info(log_msg="Conected widgets:\n" + '\n'.join([' ,parent:'.join([str(self.layout.itemAt(wid).widget()), str(self.layout.itemAt(wid).widget().parentWidget())]) for wid in xrange(self.layout.count())]))
        #utils.MessagebarAndLog.info(log_msg="All children parents:\n" + '\n'.join([': '.join([str(w), str(w.parentWidget())]) for w in self.all_children]))

    def update_observations(self, observations):

        observations = copy.deepcopy(observations)
        for parameter_name, import_method_chooser in self.parameter_imports.items():
            parameter_import_fields = import_method_chooser.parameter_import_fields
            if parameter_import_fields is not None:
                observations = parameter_import_fields.alter_data(
                    observations)
        return observations

    def filter_import_methods_not_set(self, observations):

        observations = copy.deepcopy(observations)
        #Order the observations under the import methods, and filter out the parameters not set.
        _observations = []
        for observation in observations:
            #This test is needed when the input fields have been filtered so that not all
            #parameternames exists as parameter import.
            if observation['parametername'] in self.parameter_imports:
                if self.parameter_imports[observation['parametername']].import_method and self.parameter_imports[observation['parametername']].import_method is not None:
                    _observations.append(observation)
        observations = _observations
        return observations

    def get_observations_importmethods(self, observations):
        observations = copy.deepcopy(observations)
        observations_importmethods = {}
        for observation in observations:
            if self.parameter_imports[observation['parametername']].import_method:
                observations_importmethods.setdefault(self.parameter_imports[observation['parametername']].import_method, []).append(observation)
        return observations_importmethods

    def set_parameters_using_stored_settings(self, stored_settings):
        """
        Sets the parameter settings based on a stored settings dict.

        parametername|import_method:w_flow|flowtype:Aveflow|unit:m3/s/parametername2|import_method:comment ...
        :param stored_settings: alist like [['parametername', [['attr1', 'val1'], ...]], ...]
        :return:
        """
        utils.MessagebarAndLog.info(log_msg=ru(QCoreApplication.translate('InputFields', 'Setting parameters using stored settings: %s'))%str(stored_settings))
        for import_method_chooser in list(self.parameter_imports.values()):

            if not stored_settings:
                continue
            settings = [attrs for param, attrs in stored_settings if param == import_method_chooser.parameter_name]

            if settings:
                settings = settings[0]
            else:
                continue

            if settings is None or not settings:
                continue

            import_method_chooser.import_method = [v if v else None for k, v in settings if k == 'import_method'][0]

            if import_method_chooser.parameter_import_fields is None:
                import_method_chooser.choose_method(import_method_chooser.import_method_classes)

            for attr, val in settings:
                if attr == 'import_method':
                    continue
                try:
                    setattr(import_method_chooser.parameter_import_fields, attr, val)
                except Exception as e:
                    utils.MessagebarAndLog.info(log_msg=ru(QCoreApplication.translate('InputFields', 'Setting parameter %s for %s to value %s failed, msg:\n%s'))%(str(attr), import_method_chooser.parameter_name, str(val), str(e)))

    def update_stored_settings(self, stored_settings, force_update=False):
        setted_pars = []
        new_settings = []
        for parameter_name, import_method_chooser in self.parameter_imports.items():
            if not force_update:
                if import_method_chooser.import_method is None or not import_method_chooser.import_method:
                    continue

            attrs = [('import_method', import_method_chooser.import_method)]

            parameter_import_fields = import_method_chooser.parameter_import_fields
            if parameter_import_fields is None:
                continue

            try:
                settings = parameter_import_fields.get_settings()
            except AttributeError:
                settings = tuple()

            if settings:
                attrs.extend(settings)
            new_settings.append([parameter_name, attrs])
            setted_pars.append(parameter_name)

        for parameter, attrs in stored_settings:
            if parameter not in setted_pars:
                new_settings.append([parameter, attrs])

        stored_settings[:] = new_settings

    def clear_widgets(self):
        for name, param_import_obj in self.parameter_imports.items():
            self.layout.removeWidget(param_import_obj.widget)
            param_import_obj.widget.close()
        self.parameter_imports = OrderedDict()


class ImportMethodChooser(RowEntry):
    def __init__(self, parameter_name, parameter_names):
        super(ImportMethodChooser, self).__init__()

        self.parameter_widget = None
        self.parameter_name = parameter_name
        self.parameter_names = parameter_names
        self.parameter_import_fields = None
        self.label = qgis.PyQt.QtWidgets.QLabel()
        self.label.setText(self.parameter_name)
        self.label.setTextInteractionFlags(qgis.PyQt.QtCore.Qt.TextSelectableByMouse)
        self.__import_method = qgis.PyQt.QtWidgets.QComboBox()

        self.import_method_classes = OrderedDict((('', None),
                                                  ('comments', CommentsImportFields),
                                                  ('w_levels', WLevelsImportFields),
                                                  ('w_flow', WFlowImportFields),
                                                  ('w_qual_field_depth', WQualFieldDepthImportFields),
                                                  ('w_qual_field', WQualFieldImportFields)))

        self.__import_method.addItems(list(self.import_method_classes.keys()))

        self.__import_method.currentIndexChanged.connect(
                     lambda: self.choose_method(self.import_method_classes))

        for widget in [self.label, self.__import_method]:
            self.layout.addWidget(widget)

        self.layout.insertStretch(-1, 0)

    @property
    def import_method(self):
        return str(self.__import_method.currentText())

    @import_method.setter
    def import_method(self, value):
        index = self.__import_method.findText(ru(value))
        if index != -1:
            self.__import_method.setCurrentIndex(index)

    def choose_method(self, import_methods_classes):
        import_method_name = self.import_method
        #Remove stretch
        self.layout.takeAt(-1)
        try:
            self.layout.removeWidget(self.parameter_widget)
        except Exception as e:
            pass
        try:
            self.parameter_widget.close()
        except Exception as e:
            pass
        try:
            self.parameter_import_fields = None
        except Exception as e:
            pass

        parameter_import_fields_class = import_methods_classes.get(import_method_name, None)

        if parameter_import_fields_class is None:
            self.parameter_widget = None
            self.parameter_import_fields = None
            self.layout.insertStretch(-1, 0)

        else:
            self.parameter_import_fields = parameter_import_fields_class(self)
            self.parameter_widget = self.parameter_import_fields.widget
            self.layout.addWidget(self.parameter_widget)

    def close(self):
        for child in self.layout.children():
            #self.layout.removeWidget(child)
            child.close()
        self.widget.close()


class CommentsImportFields(RowEntry):
    """
    """
    def __init__(self, import_method_chooser):
        """
        """
        super(CommentsImportFields, self).__init__()
        self.import_method_chooser = import_method_chooser
        self.layout.insertStretch(-1, 0)

    def alter_data(self, observations):
        observations = copy.deepcopy(observations)
        parameter_name = self.import_method_chooser.parameter_name
        comment_obsdict = {}
        dateformat = '%Y%m%d %H:%M:%S'
        for observation in observations:
            if observation['parametername'] == parameter_name:
                datestring = datetime.strftime(observation['date_time'], dateformat)
                comment_obsdict.setdefault(observation['sublocation'], {})[datestring] = observation

        for observation in observations:
            if observation['parametername'] != parameter_name:
                datestring = datetime.strftime(observation['date_time'], dateformat)
                comment_obs = comment_obsdict.get(observation['sublocation'], {}).get(datestring, None)
                if comment_obs != None:
                    observation['comment'] = comment_obs['value']
                    comment_obs['skip_comment_import'] = True

        return observations


class WLevelsImportFields(RowEntryGrid):
    """
    """

    def __init__(self, import_method_chooser):
        """
        """
        super(WLevelsImportFields, self).__init__()

        self.h_toc_dict = None
        self.import_method_chooser = import_method_chooser
        self.label_value_column = qgis.PyQt.QtWidgets.QLabel('Value column: ')
        self._value_column = qgis.PyQt.QtWidgets.QComboBox()
        self._calculate_level_masl_checkbox = qgis.PyQt.QtWidgets.QCheckBox(ru(QCoreApplication.translate('WLevelsImportFields', 'Calculate level_masl from meas and h_toc')))
        self._calculate_level_masl_checkbox.setToolTip(ru(QCoreApplication.translate('WLevelsImportFields', 'If h_toc is not NULL in table obs_points, level_masl is calculated as h_toc - meas.')))
        self._value_column.addItems(['meas', 'level_masl'])
        self.value_column = 'meas'
        self.layout.addWidget(self.label_value_column, 0, 0)
        self.layout.addWidget(self._value_column, 1, 0)
        self.layout.addWidget(self._calculate_level_masl_checkbox, 1, 1)
        self.layout.setColumnStretch(1, 2)

        self._value_column.currentIndexChanged.connect(self.set_calculate_level_masl_visibility)

        self.set_calculate_level_masl_visibility()

    @property
    def value_column(self):
        return str(self._value_column.currentText())

    @value_column.setter
    def value_column(self, value):
        index = self._value_column.findText(ru(value))
        if index != -1:
            self._value_column.setCurrentIndex(index)
        if value == 'meas':
            self.calculate_level_masl = True
        else:
            self.calculate_level_masl = False
        self.set_calculate_level_masl_visibility()

    @property
    def calculate_level_masl(self):
        return self._calculate_level_masl_checkbox.isChecked()

    @calculate_level_masl.setter
    def calculate_level_masl(self, a_bool):
        if a_bool:
            self._calculate_level_masl_checkbox.setChecked(True)
        else:
            self._calculate_level_masl_checkbox.setChecked(False)

    def set_calculate_level_masl_visibility(self):
        if self.value_column == 'meas':
            self._calculate_level_masl_checkbox.setVisible(True)
        else:
            self._calculate_level_masl_checkbox.setVisible(False)

    def alter_data(self, observations):
        for observation in observations:
            if observation['parametername'] == self.import_method_chooser.parameter_name:
                if self.value_column == 'level_masl':
                    observation['level_masl'] = observation['value']
                else:
                    observation['meas'] = observation['value'].replace(',', '.')

                    if self.calculate_level_masl:
                        if self.h_toc_dict is None:
                            self.h_toc_dict = dict([(obsid_h_toc[0], obsid_h_toc[1]) for obsid_h_toc in db_utils.sql_load_fr_db('SELECT obsid, h_toc FROM obs_points WHERE h_toc IS NOT NULL')[1]])
                        h_toc = self.h_toc_dict.get(observation['obsid'], None)
                        if h_toc is not None:
                            observation['level_masl'] = str(float(h_toc) - float(observation['meas']))
                            observation['h_toc'] = str(float(h_toc))
        return observations

    def get_settings(self):
        return (('value_column', self.value_column), )


class WFlowImportFields(RowEntryGrid):
    """
    This class should create a layout and populate it with question boxes relevant to w_flow import which is probably "flowtype" and "unit" dropdown lists.
    """


    def __init__(self, import_method_chooser):
        """
        A HBoxlayout should be created as self.layout.
        It shuold also create an empty list for future data as self.data
        Connecting the dropdown lists as events is done here (or in submethods).
        """
        super(WFlowImportFields, self).__init__()

        self._import_method_chooser = import_method_chooser
        self.label_flowtype = qgis.PyQt.QtWidgets.QLabel('Flowtype: ')
        self.__flowtype = default_combobox()
        self._flowtypes_units = defs.w_flow_flowtypes_units()
        self.__flowtype.addItems(sorted(self._flowtypes_units.keys()))
        self.label_unit = qgis.PyQt.QtWidgets.QLabel('Unit: ')
        self.__unit = default_combobox()
        self.__flowtype.editTextChanged.connect(
                     lambda : self.fill_list(self.__unit, self.flowtype, self._flowtypes_units))

        self.layout.addWidget(self.label_flowtype, 0, 0)
        self.layout.addWidget(self.__flowtype, 1, 0)
        self.layout.addWidget(self.label_unit, 0, 1)
        self.layout.addWidget(self.__unit, 1, 1)
        self.layout.setColumnStretch(2, 1)

        #self.layout.addStretch()

    @property
    def flowtype(self):
        return ru(self.__flowtype.currentText())

    @flowtype.setter
    def flowtype(self, value):
        self.__flowtype.setEditText(value)

    @property
    def unit(self):
        return ru(self.__unit.currentText())

    @unit.setter
    def unit(self, value):
        self.__unit.setEditText(ru(value))

    def fill_list(self, combobox_var, parameter_var, parameter_list_dict):
        """

        :param combobox_var: a QComboBox object
        :param parameter_var: a string parameter name
        :param parameter_list_dict: A dict like  {'Accvol': [('m3',)], 'Momflow': [('l/s',)]}
        :return:
        """
        vals = parameter_list_dict.get(parameter_var, None)
        if vals is None:
            vals = list(sorted(set([val for vals_list in list(parameter_list_dict.values()) for val in vals_list[0]])))
        else:
            vals = list(vals[0])
        combobox_var.clear()
        combobox_var.addItem('')
        combobox_var.addItems(ru(vals, keep_containers=True))

    def get_settings(self):
        return (('flowtype', self.flowtype), ('unit', self.unit))

    def alter_data(self, observations):
        if not self.flowtype:
            raise utils.UsageError(ru(QCoreApplication.translate('WFlowImportFields', 'Import error, flowtype not given')))
        if not self.unit:
            raise utils.UsageError(ru(QCoreApplication.translate('WFlowImportFields', 'Import error, unit not given')))

        observations = copy.deepcopy(observations)
        for observation in observations:
            if observation['parametername'] == self._import_method_chooser.parameter_name:
                observation['flowtype'] = self.flowtype
                observation['unit'] = self.unit

        return observations


class WQualFieldImportFields(RowEntryGrid):
    """
    This class should create a layout and populate it with question boxes relevant to w_qual_fields import which is probably "parameter", "unit" dropdown lists.
    And a depth dropdown list which is populated by the parameternames. The purpose is that the user should select which parametername to use as the depth variable

    """

    def __init__(self, import_method_chooser):
        """
        A HBoxlayout should be created as self.layout.
        It shuold also create an empty list for future data as self.data
        Connecting the dropdown lists as events is done here (or in submethods).
        """
        super(WQualFieldImportFields, self).__init__()

        self._import_method_chooser = import_method_chooser
        self.label_parameter = qgis.PyQt.QtWidgets.QLabel(ru(QCoreApplication.translate('WQualFieldImportFields', 'Parameter: ')))
        self.__parameter = default_combobox()
        self._parameters_units = defs.w_qual_field_parameter_units()
        self.__parameter.addItems(list(self._parameters_units.keys()))
        self.label_unit = qgis.PyQt.QtWidgets.QLabel(ru(QCoreApplication.translate('WQualFieldImportFields', 'Unit: ')))
        self.__unit = default_combobox()
        self.__instrument = default_combobox()
        self.label_instrument = qgis.PyQt.QtWidgets.QLabel(ru(QCoreApplication.translate('WQualFieldImportFields', 'Instrument: ')))
        self.parameter_instruments = {}
        for parameter, unit_instrument_staff_date_time_list_of_lists in definitions.midvatten_defs.get_last_used_quality_instruments().items():
            for unit, instrument, staff, date_time, in unit_instrument_staff_date_time_list_of_lists:
                self.parameter_instruments.setdefault(parameter, set()).add(instrument)

        for parameter, instrument_set in self.parameter_instruments.items():
            self.parameter_instruments[parameter] = list(instrument_set)

        self.layout.addWidget(self.label_parameter, 0, 0)
        self.layout.addWidget(self.__parameter, 1, 0)
        self.layout.addWidget(self.label_unit, 0, 1)
        self.layout.addWidget(self.__unit, 1, 1)
        self.layout.addWidget(self.label_instrument, 0, 3)
        self.layout.addWidget(self.__instrument, 1, 3)
        self.layout.setColumnStretch(4, 1)

        self.__parameter.editTextChanged.connect(
                     lambda : self.fill_list(self.__unit, self.parameter, self._parameters_units))

        self.__parameter.editTextChanged.connect(
                     lambda: self.fill_list(self.__instrument, self.parameter, self.parameter_instruments))

    @property
    def parameter(self):
        return ru(self.__parameter.currentText())

    @parameter.setter
    def parameter(self, value):
        self.__parameter.setEditText(value)

    @property
    def unit(self):
        return ru(self.__unit.currentText())

    @unit.setter
    def unit(self, value):
        self.__unit.setEditText(ru(value))

    @property
    def instrument(self):
        return ru(self.__instrument.currentText())

    @instrument.setter
    def instrument(self, value):
        self.__instrument.setEditText(ru(value))

    def fill_list(self, combobox_var, parameter_var, parameter_list_dict):
        """

        :param combobox_var: a QComboBox object
        :param parameter_var: a string parameter name
        :param parameter_list_dict: A dict like  {'Accvol': [('m3',)], 'Momflow': [('l/s',)]}
        :return:
        """
        vals = parameter_list_dict.get(parameter_var, None)
        if vals is None:
            vals = list(sorted(set([val[0] if isinstance(val, (list, tuple)) else val for vals_list in list(parameter_list_dict.values()) for val in vals_list])))
        else:
            vals = sorted([val[0] if isinstance(val, (list, tuple)) else val for val in vals])

        combobox_var.clear()
        combobox_var.addItem('')
        combobox_var.addItems(ru(vals, keep_containers=True))

    def get_settings(self):
        return (('parameter', self.parameter),
                           ('unit', self.unit),
                           ('depth', self.depth),
                           ('instrument', self.instrument))

    def alter_data(self, observations):
        if not self.parameter:
            raise utils.UsageError(ru(QCoreApplication.translate('WQualFieldImportFields', 'Import error, parameter not given')))

        observations = copy.deepcopy(observations)

        """
        #Only for dev
        adepth_dict = {}
        try:
            for obs in observations:
                utils.MessagebarAndLog.info(log_msg="Obs: " + str(obs))
                if obs['parametername'] == self.depth:
                    adepth_dict[obs['date_time']] = obs['value']
        except TypeError, e:
            raise Exception("Obs: " + str(obs) + " e " + str(e))
        """
        for observation in observations:
            try:
                if observation['parametername'] == self._import_method_chooser.parameter_name:
                    observation['parameter'] = self.parameter
                    observation['instrument'] = self.instrument
                    observation['unit'] = self.unit
            except TypeError:
                utils.MessagebarAndLog.critical(bar_msg=ru(QCoreApplication.translate('WQualFieldImportFields', "Import error. See message log panel")),
                                                log_msg=ru(QCoreApplication.translate('WQualFieldImportFields', "error on observation : %s\nand parameter: %s"))%(str(observation), self.parameter))
                raise TypeError
        return observations


class WQualFieldDepthImportFields(RowEntry):
    """
    """
    def __init__(self, import_method_chooser):
        """
        """
        super(WQualFieldDepthImportFields, self).__init__()
        self.import_method_chooser = import_method_chooser
        self.layout.insertStretch(-1, 0)

    def alter_data(self, observations):
        #Depth should be added for all observations with the same obsid and date_time

        observations = copy.deepcopy(observations)

        parameter_name = self.import_method_chooser.parameter_name

        dateformat = '%Y%m%d %H:%M:%S'
        depths = dict([((obs['sublocation'], datetime.strftime(obs['date_time'], dateformat)), obs['value'])
                       for obs in observations if obs['parametername'] == parameter_name])
        if not depths:
            return observations

        for observation in observations:
            depth = depths.get((observation['sublocation'], datetime.strftime(observation['date_time'], dateformat)), None)
            if depth is not None:
                observation['depth'] = depth

        return observations


def default_combobox(editable=True):
    combo_box = qgis.PyQt.QtWidgets.QComboBox()
    combo_box.setEditable(editable)
    combo_box.setSizeAdjustPolicy(qgis.PyQt.QtWidgets.QComboBox.AdjustToContents)
    combo_box.setMinimumWidth(80)
    combo_box.addItem('')
    return combo_box

