# -*- coding: utf-8 -*-
"""
/***************************************************************************
 This part of the Midvatten plugin tests the module that handles calibration
 of logger data.

                             -------------------
        begin                : 2016-03-08
        copyright            : (C) 2016 by joskal (HenrikSpa)
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
import mock
from nose.plugins.attrib import attr
import db_utils
import gui_utils
import date_utils
import utils_for_tests
from wlevels_calc_calibr import Calibrlogger


@attr(status='on')
class TestCalibrlogger(utils_for_tests.MidvattenTestPostgisDbSv):
    """ Test to make sure wlvllogg_import goes all the way to the end without errors
    """
    @mock.patch('midvatten_utils.MessagebarAndLog')
    @mock.patch('db_utils.QgsProject.instance', utils_for_tests.MidvattenTestPostgisNotCreated.mock_instance_settings_database)
    @mock.patch('db_utils.get_postgis_connections', utils_for_tests.MidvattenTestPostgisNotCreated.mock_postgis_connections)
    def test_calibrlogger_last_calibration(self, mock_messagebar):
        db_utils.sql_alter_db(u"INSERT INTO obs_points (obsid) VALUES ('rb1')")
        db_utils.sql_alter_db(u"INSERT INTO w_levels_logger (obsid, date_time, head_cm, level_masl) VALUES ('rb1', '2017-02-01 00:00', 50, 100)")
        db_utils.sql_alter_db(u"INSERT INTO w_levels_logger (obsid, date_time, head_cm, level_masl) VALUES ('rb1', '2017-03-01 00:00', 100, NULL)")
        calibrlogger = Calibrlogger(self.iface.mainWindow(), self.ms)

        calibrlogger.update_plot()
        test = utils_for_tests.create_test_string(calibrlogger.getlastcalibration(calibrlogger.selected_obsid))
        ref = u'[(2017-02-01 00:00, 99.5)]'
        assert test == ref


    @mock.patch('midvatten_utils.MessagebarAndLog')
    @mock.patch('db_utils.QgsProject.instance', utils_for_tests.MidvattenTestPostgisNotCreated.mock_instance_settings_database)
    @mock.patch('db_utils.get_postgis_connections', utils_for_tests.MidvattenTestPostgisNotCreated.mock_postgis_connections)
    def test_calibrlogger_set_log_pos(self, mock_messagebar):
        db_utils.sql_alter_db(u"INSERT INTO obs_points (obsid) VALUES ('rb1')")
        db_utils.sql_alter_db(u"INSERT INTO w_levels (obsid, date_time, level_masl) VALUES ('rb1', '2017-02-01 00:00', 100)")
        db_utils.sql_alter_db(u"INSERT INTO w_levels_logger (obsid, date_time, head_cm) VALUES ('rb1', '2017-02-01 00:00', 100)")

        calibrlogger = Calibrlogger(self.iface.mainWindow(), self.ms)
        calibrlogger.update_plot()

        calibrlogger.FromDateTime.setDateTime(date_utils.datestring_to_date(u'2000-01-01 00:00:00'))
        calibrlogger.LoggerPos.setText(u'2')
        gui_utils.set_combobox(calibrlogger.combobox_obsid, u'rb1 (uncalibrated)')

        calibrlogger.set_logger_pos()
        print(str(mock_messagebar.mock_calls))
        test = utils_for_tests.create_test_string(db_utils.sql_load_fr_db(u'SELECT * FROM w_levels_logger'))
        ref = u'(True, [(rb1, 2017-02-01 00:00, 100.0, None, None, 3.0, None)])'
        print(test)
        assert test == ref


    @mock.patch('midvatten_utils.MessagebarAndLog')
    @mock.patch('db_utils.QgsProject.instance', utils_for_tests.MidvattenTestPostgisNotCreated.mock_instance_settings_database)
    @mock.patch('db_utils.get_postgis_connections', utils_for_tests.MidvattenTestPostgisNotCreated.mock_postgis_connections)
    def test_calibrlogger_add_to_level_masl(self, mock_messagebar):
        db_utils.sql_alter_db(u"INSERT INTO obs_points (obsid) VALUES ('rb1')")
        db_utils.sql_alter_db(u"INSERT INTO w_levels_logger (obsid, date_time, level_masl) VALUES ('rb1', '2017-02-01 00:00', 100)")
        calibrlogger = Calibrlogger(self.iface.mainWindow(), self.ms)

        calibrlogger.update_plot()

        calibrlogger.FromDateTime.setDateTime(date_utils.datestring_to_date(u'2000-01-01 00:00:00'))
        calibrlogger.Add2Levelmasl.setText(u'50')
        gui_utils.set_combobox(calibrlogger.combobox_obsid, u'rb1 (uncalibrated)')

        calibrlogger.add_to_level_masl()

        test = utils_for_tests.create_test_string(db_utils.sql_load_fr_db(u'SELECT * FROM w_levels_logger'))
        ref = u'(True, [(rb1, 2017-02-01 00:00, None, None, None, 150.0, None)])'
        print(test)
        assert test == ref

    @mock.patch('wlevels_calc_calibr.utils.pop_up_info', autospec=True)
    @mock.patch('midvatten_utils.MessagebarAndLog')
    @mock.patch('db_utils.QgsProject.instance', utils_for_tests.MidvattenTestPostgisNotCreated.mock_instance_settings_database)
    @mock.patch('db_utils.get_postgis_connections', utils_for_tests.MidvattenTestPostgisNotCreated.mock_postgis_connections)
    def test_calibrlogger_calc_best_fit_log_pos_out_of_radius(self, mock_messagebar, skip_popup):
        db_utils.sql_alter_db(u"INSERT INTO obs_points (obsid) VALUES ('rb1')")
        db_utils.sql_alter_db(u"INSERT INTO w_levels (obsid, date_time, level_masl) VALUES ('rb1', '2017-02-01 00:00', 100)")
        db_utils.sql_alter_db(u"INSERT INTO w_levels_logger (obsid, date_time, head_cm) VALUES ('rb1', '2017-03-01 00:00', 50)")
        calibrlogger = Calibrlogger(self.iface.mainWindow(), self.ms)

        calibrlogger.update_plot()

        calibrlogger.loggerpos_masl_or_offset_state = 1
        calibrlogger.FromDateTime.setDateTime(date_utils.datestring_to_date(u'2000-01-01 00:00:00'))
        gui_utils.set_combobox(calibrlogger.combobox_obsid, u'rb1 (uncalibrated)')

        calibrlogger.calc_best_fit()

        test = utils_for_tests.create_test_string(db_utils.sql_load_fr_db(u'SELECT * FROM w_levels_logger'))
        ref = u'(True, [(rb1, 2017-03-01 00:00, 50.0, None, None, None, None)])'
        print(test)
        assert test == ref

    @mock.patch('wlevels_calc_calibr.utils.pop_up_info', autospec=True)
    @mock.patch('midvatten_utils.MessagebarAndLog')
    @mock.patch('db_utils.QgsProject.instance', utils_for_tests.MidvattenTestPostgisNotCreated.mock_instance_settings_database)
    @mock.patch('db_utils.get_postgis_connections', utils_for_tests.MidvattenTestPostgisNotCreated.mock_postgis_connections)
    def test_calibrlogger_calc_best_fit_log_pos(self, mock_messagebar, skip_popup):
        db_utils.sql_alter_db(u"INSERT INTO obs_points (obsid) VALUES ('rb1')")
        db_utils.sql_alter_db(u"INSERT INTO w_levels (obsid, date_time, level_masl) VALUES ('rb1', '2017-02-01 00:00', 100)")
        db_utils.sql_alter_db(u"INSERT INTO w_levels_logger (obsid, date_time, head_cm) VALUES ('rb1', '2017-02-01 01:00', 50)")
        calibrlogger = Calibrlogger(self.iface.mainWindow(), self.ms)

        calibrlogger.update_plot()

        calibrlogger.loggerpos_masl_or_offset_state = 1
        calibrlogger.FromDateTime.setDateTime(date_utils.datestring_to_date(u'2000-01-01 00:00:00'))
        gui_utils.set_combobox(calibrlogger.combobox_obsid, u'rb1 (uncalibrated)')
        calibrlogger.bestFitSearchRadius.setText(u'2 hours')

        calibrlogger.calc_best_fit()

        test = utils_for_tests.create_test_string(db_utils.sql_load_fr_db(u'SELECT * FROM w_levels_logger'))
        ref = u'(True, [(rb1, 2017-02-01 01:00, 50.0, None, None, 100.0, None)])'
        print(test)
        assert test == ref

    @mock.patch('wlevels_calc_calibr.utils.pop_up_info', autospec=True)
    @mock.patch('midvatten_utils.MessagebarAndLog')
    @mock.patch('db_utils.QgsProject.instance', utils_for_tests.MidvattenTestPostgisNotCreated.mock_instance_settings_database)
    @mock.patch('db_utils.get_postgis_connections', utils_for_tests.MidvattenTestPostgisNotCreated.mock_postgis_connections)
    def test_calibrlogger_calc_best_fit_add(self, mock_messagebar, skip_popup):
        db_utils.sql_alter_db(u"INSERT INTO obs_points (obsid) VALUES ('rb1')")
        db_utils.sql_alter_db(u"INSERT INTO w_levels (obsid, date_time, level_masl) VALUES ('rb1', '2017-02-01 00:00', 100)")
        db_utils.sql_alter_db(u"INSERT INTO w_levels_logger (obsid, date_time, level_masl) VALUES ('rb1', '2017-02-01 01:00', 50)")
        calibrlogger = Calibrlogger(self.iface.mainWindow(), self.ms)

        calibrlogger.update_plot()

        calibrlogger.loggerpos_masl_or_offset_state = 2
        calibrlogger.FromDateTime.setDateTime(date_utils.datestring_to_date(u'2000-01-01 00:00:00'))
        gui_utils.set_combobox(calibrlogger.combobox_obsid, u'rb1 (uncalibrated)')
        calibrlogger.bestFitSearchRadius.setText(u'2 hours')

        calibrlogger.calc_best_fit()

        test = utils_for_tests.create_test_string(db_utils.sql_load_fr_db(u'SELECT * FROM w_levels_logger'))
        ref = u'(True, [(rb1, 2017-02-01 01:00, None, None, None, 100.0, None)])'
        print(test)
        assert test == ref

    @mock.patch('wlevels_calc_calibr.utils.pop_up_info', autospec=True)
    @mock.patch('midvatten_utils.MessagebarAndLog')
    @mock.patch('db_utils.QgsProject.instance', utils_for_tests.MidvattenTestPostgisNotCreated.mock_instance_settings_database)
    @mock.patch('db_utils.get_postgis_connections', utils_for_tests.MidvattenTestPostgisNotCreated.mock_postgis_connections)
    def test_calibrlogger_calc_best_fit_add_no_matches_same_from_date(self, mock_messagebar, skip_popup):
        db_utils.sql_alter_db(u"INSERT INTO obs_points (obsid) VALUES ('rb1')")
        db_utils.sql_alter_db(u"INSERT INTO w_levels (obsid, date_time, level_masl) VALUES ('rb1', '2017-02-01 00:00', 100)")
        db_utils.sql_alter_db(u"INSERT INTO w_levels_logger (obsid, date_time, level_masl) VALUES ('rb1', '2017-02-01 01:00', 50)")
        calibrlogger = Calibrlogger(self.iface.mainWindow(), self.ms)

        calibrlogger.update_plot()

        calibrlogger.loggerpos_masl_or_offset_state = 2
        calibrlogger.FromDateTime.setDateTime(date_utils.datestring_to_date(u'2017-02-01 01:00'))
        gui_utils.set_combobox(calibrlogger.combobox_obsid, u'rb1 (uncalibrated)')
        calibrlogger.bestFitSearchRadius.setText(u'2 hours')

        calibrlogger.calc_best_fit()

        test = utils_for_tests.create_test_string(db_utils.sql_load_fr_db(u'SELECT * FROM w_levels_logger'))
        ref = u'(True, [(rb1, 2017-02-01 01:00, None, None, None, 50.0, None)])'
        print(test)
        assert test == ref

    @mock.patch('wlevels_calc_calibr.utils.pop_up_info', autospec=True)
    @mock.patch('midvatten_utils.MessagebarAndLog')
    @mock.patch('db_utils.QgsProject.instance', utils_for_tests.MidvattenTestPostgisNotCreated.mock_instance_settings_database)
    @mock.patch('db_utils.get_postgis_connections', utils_for_tests.MidvattenTestPostgisNotCreated.mock_postgis_connections)
    def test_calibrlogger_calc_best_fit_add_no_matches_same_to_date(self, mock_messagebar, skip_popup):
        db_utils.sql_alter_db(u"INSERT INTO obs_points (obsid) VALUES ('rb1')")
        db_utils.sql_alter_db(u"INSERT INTO w_levels (obsid, date_time, level_masl) VALUES ('rb1', '2017-02-01 00:00', 100)")
        db_utils.sql_alter_db(u"INSERT INTO w_levels_logger (obsid, date_time, level_masl) VALUES ('rb1', '2017-02-01 01:00', 50)")
        calibrlogger = Calibrlogger(self.iface.mainWindow(), self.ms)

        calibrlogger.update_plot()

        calibrlogger.loggerpos_masl_or_offset_state = 2
        calibrlogger.FromDateTime.setDateTime(date_utils.datestring_to_date(u'2010-02-01 01:00'))
        calibrlogger.ToDateTime.setDateTime(date_utils.datestring_to_date(u'2017-02-01 01:00'))
        gui_utils.set_combobox(calibrlogger.combobox_obsid, u'rb1 (uncalibrated)')
        calibrlogger.bestFitSearchRadius.setText(u'2 hours')

        calibrlogger.calc_best_fit()

        test = utils_for_tests.create_test_string(db_utils.sql_load_fr_db(u'SELECT * FROM w_levels_logger'))
        ref = u'(True, [(rb1, 2017-02-01 01:00, None, None, None, 50.0, None)])'
        print(test)
        assert test == ref
