# -*- coding: utf-8 -*-
"""
/***************************************************************************
 This part of the Midvatten plugin tests the module that handles often used
 utilities.

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
from __future__ import absolute_import
from builtins import str
from builtins import object
import io

import db_utils
import midvatten_utils as utils
import mock
import nose
from nose.plugins.attrib import attr

import utils_for_tests
from mocks_for_tests import MockUsingReturnValue
from .utils_for_tests import create_test_string


@attr(status='only')
class TestFilterNonexistingObsidsAndAsk(object):
    @mock.patch('qgis.utils.iface', autospec=True)
    @mock.patch('midvatten_utils.NotFoundQuestion', autospec=True)
    def test_filter_nonexisting_obsids_and_ask_ok(self, mock_notfound, mock_iface):
            mock_notfound.return_value.answer = 'ok'
            mock_notfound.return_value.value = 10
            mock_notfound.return_value.reuse_column = 'obsid'
            file_data = [['obsid', 'ae'], ['1', 'b'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g'], ['21', 'h']]
            existing_obsids = ['2', '3', '10', '1_g', '1 a']
            filtered_file_data = utils.filter_nonexisting_values_and_ask(file_data, 'obsid', existing_obsids)
            reference_list = [['obsid', 'ae'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g'], ['10', 'b'], ['10', 'h']]
            assert filtered_file_data == reference_list

    @mock.patch('qgis.utils.iface', autospec=True)
    @mock.patch('midvatten_utils.NotFoundQuestion', autospec=True)
    def test_filter_nonexisting_obsids_and_ask_cancel(self, mock_notfound, mock_iface):
            mock_notfound.return_value.answer = 'cancel'
            mock_notfound.return_value.value = 10
            mock_notfound.return_value.reuse_column = 'obsid'
            file_data = [['obsid', 'ae'], ['1', 'b'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g'], ['21', 'h']]
            existing_obsids = ['2', '3', '10', '1_g', '1 a']
            nose.tools.assert_raises(utils.UserInterruptError, utils.filter_nonexisting_values_and_ask, file_data, 'obsid', existing_obsids)

    @mock.patch('qgis.utils.iface', autospec=True)
    @mock.patch('midvatten_utils.NotFoundQuestion', autospec=True)
    def test_filter_nonexisting_obsids_and_ask_skip(self, mock_notfound, mock_iface):
            mock_notfound.return_value.answer = 'skip'
            mock_notfound.return_value.value = 10
            mock_notfound.return_value.reuse_column = 'obsid'
            file_data = [['obsid', 'ae'], ['1', 'b'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g'], ['21', 'h']]
            existing_obsids = ['2', '3', '10', '1_g', '1 a']
            filtered_file_data = utils.filter_nonexisting_values_and_ask(file_data, 'obsid', existing_obsids)
            reference_list = [['obsid', 'ae'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g']]
            assert filtered_file_data == reference_list

    @mock.patch('qgis.utils.iface', autospec=True)
    @mock.patch('midvatten_utils.NotFoundQuestion', autospec=True)
    def test_filter_nonexisting_obsids_and_ask_none_value_skip(self, mock_notfound, mock_iface):
            mock_notfound.return_value.answer = 'skip'
            mock_notfound.return_value.value = 10
            mock_notfound.return_value.reuse_column = 'obsid'
            file_data = [['obsid', 'ae'], ['1', 'b'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g'], [None, 'h']]
            existing_obsids = ['2', '3', '10', '1_g', '1 a']
            filtered_file_data = utils.filter_nonexisting_values_and_ask(file_data, 'obsid', existing_obsids)
            reference_list = [['obsid', 'ae'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g']]
            assert filtered_file_data == reference_list

    @mock.patch('qgis.utils.iface', autospec=True)
    @mock.patch('midvatten_utils.NotFoundQuestion', autospec=True)
    def test_filter_nonexisting_obsids_and_ask_header_not_found(self, mock_notfound, mock_iface):
        """If a asked for header column is not found, it's added to the end of the rows."""
        mock_notfound.return_value.answer = 'ok'
        mock_notfound.return_value.value = 10
        mock_notfound.return_value.reuse_column = 'obsid'
        file_data = [['obsid', 'ae'], ['1', 'b'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g'], ['21', 'h']]
        existing_obsids = ['2', '3', '10', '1_g', '1 a']
        filtered_file_data = utils.filter_nonexisting_values_and_ask(file_data, 'header_that_should_not_exist', existing_obsids)
        reference_list = [['obsid', 'ae', 'header_that_should_not_exist'], ['1', 'b', '10'], ['2', 'c', '10'], ['3', 'd', '10'], ['10', 'e', '10'], ['1_g', 'f', '10'], ['1 a', 'g', '10'], ['21', 'h', '10']]
        assert filtered_file_data == reference_list

    @mock.patch('qgis.utils.iface', autospec=True)
    def test_filter_nonexisting_obsids_and_ask_header_capitalize(self, mock_iface):
            file_data = [['obsid', 'ae'], ['a', 'b'], ['2', 'c']]
            existing_obsids = ['A', '2']
            filtered_file_data = utils.filter_nonexisting_values_and_ask(file_data=file_data, header_value='obsid', existing_values=existing_obsids, try_capitalize=True, always_ask_user=False)
            reference_list = [['obsid', 'ae'], ['A', 'b'], ['2', 'c']]
            assert filtered_file_data == reference_list

    @mock.patch('qgis.utils.iface', autospec=True)
    @mock.patch('midvatten_utils.NotFoundQuestion', autospec=True)
    def test_filter_nonexisting_obsids_only_ask_once(self, mock_notfound, mock_iface):
            mock_notfound.return_value.answer = 'ok'
            mock_notfound.return_value.value = 10
            mock_notfound.return_value.reuse_column = 'obsid'
            file_data = [['obsid', 'ae'], ['1', 'b'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g'], ['21', 'h'], ['1', 'i']]
            existing_obsids = ['2', '3', '10', '1_g', '1 a']
            filtered_file_data = utils.filter_nonexisting_values_and_ask(file_data, 'obsid', existing_obsids)
            reference_list = [['obsid', 'ae'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g'], ['10', 'b'], ['10', 'h'], ['10', 'i']]
            assert filtered_file_data == reference_list
            #The mock should only be called twice. First for 1, then for 21, and then 1 again should use the already given answer.
            assert len(mock_notfound.mock_calls) == 2

    @mock.patch('qgis.utils.iface', autospec=True)
    @mock.patch('midvatten_utils.NotFoundQuestion', autospec=True)
    def test_filter_nonexisting_obsids_and_ask_skip_only_ask_once(self, mock_notfound, mock_iface):
            mock_notfound.return_value.answer = 'skip'
            mock_notfound.return_value.value = 10
            mock_notfound.return_value.reuse_column = 'obsid'
            file_data = [['obsid', 'ae'], ['1', 'b'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g'], ['21', 'h'], ['1', 'i']]
            existing_obsids = ['2', '3', '10', '1_g', '1 a']
            filtered_file_data = utils.filter_nonexisting_values_and_ask(file_data, 'obsid', existing_obsids)
            reference_list = [['obsid', 'ae'], ['2', 'c'], ['3', 'd'], ['10', 'e'], ['1_g', 'f'], ['1 a', 'g']]
            assert filtered_file_data == reference_list
            #The mock should only be called twice. First for 1, then for 21, and then 1 again should use the already given answer.
            assert len(mock_notfound.mock_calls) == 2

@attr(status='only')
class TestTempinput(object):
    def test_tempinput(self):
        rows = '543\n21'
        with utils.tempinput(rows) as filename:
            with io.open(filename, 'r', encoding='utf-8') as f:
                res = f.readlines()
        reference_list = ['543\n', '21']
        assert res == reference_list

@attr(status='only')
class TestAskUser(object):
    qgis_PyQt_QtGui_QInputDialog_getText = MockUsingReturnValue(['-1 hours'])
    cancel = MockUsingReturnValue([''])

    @mock.patch('qgis.PyQt.QtWidgets.QInputDialog.getText', qgis_PyQt_QtGui_QInputDialog_getText.get_v)
    def test_askuser_dateshift(self):
        question = utils.Askuser('DateShift')
        assert question.result == ['-1', 'hours']

    @mock.patch('qgis.PyQt.QtWidgets.QInputDialog.getText', cancel.get_v)
    def test_askuser_dateshift_cancel(self):
        question = utils.Askuser('DateShift')
        assert question.result == 'cancel'

@attr(status='only')
class TestGetFunctions(utils_for_tests.MidvattenTestSpatialiteDbSv):
    @mock.patch('db_utils.QgsProject.instance', utils_for_tests.MidvattenTestSpatialiteNotCreated.mock_instance_settings_database)
    def test_get_last_logger_dates(self):
        db_utils.sql_alter_db('''INSERT INTO obs_points (obsid) VALUES ('rb1')''')
        db_utils.sql_alter_db('''INSERT INTO obs_points (obsid) VALUES ('rb2')''')
        db_utils.sql_alter_db('''INSERT INTO w_levels_logger (obsid, date_time) VALUES ('rb1', '2015-01-01 00:00')''')
        db_utils.sql_alter_db('''INSERT INTO w_levels_logger (obsid, date_time) VALUES ('rb1', '2015-01-01 00:00:00')''')
        db_utils.sql_alter_db('''INSERT INTO w_levels_logger (obsid, date_time) VALUES ('rb1', '2014-01-01 00:00:00')''')
        db_utils.sql_alter_db('''INSERT INTO w_levels_logger (obsid, date_time) VALUES ('rb2', '2013-01-01 00:00:00')''')
        db_utils.sql_alter_db('''INSERT INTO w_levels_logger (obsid, date_time) VALUES ('rb2', '2016-01-01 00:00')''')

        test_string = create_test_string(utils.get_last_logger_dates())
        reference_string = '''{rb1: [(2015-01-01 00:00:00)], rb2: [(2016-01-01 00:00)]}'''
        assert test_string == reference_string

@attr(status='only')
class TestSqlToParametersUnitsTuple(object):
    @mock.patch('db_utils.sql_load_fr_db', autospec=True)
    def test_sql_to_parameters_units_tuple(self, mock_sqlload):
        mock_sqlload.return_value = (True, [('par1', 'un1'), ('par2', 'un2')])

        test_string = create_test_string(utils.sql_to_parameters_units_tuple('sql'))
        reference_string = '''((par1, (un1)), (par2, (un2)))'''
        assert test_string == reference_string

@attr(status='only')
class TestCalculateDbTableRows(utils_for_tests.MidvattenTestSpatialiteDbSv):
    @mock.patch('midvatten_utils.MessagebarAndLog')
    @mock.patch('db_utils.QgsProject.instance', utils_for_tests.MidvattenTestSpatialiteNotCreated.mock_instance_settings_database)
    def test_get_db_statistics(self, mock_messagebar):
        """
        Test that calculate_db_table_rows can be run without major error
        :param mock_iface:
        :return:
        """
        utils.calculate_db_table_rows()

        assert len(str(mock_messagebar.mock_calls[0])) > 1500 and 'about_db' in str(mock_messagebar.mock_calls[0])

@attr(status='only')
class TestGetCurrentLocale(object):
    @mock.patch('locale.getdefaultlocale')
    @mock.patch('midvatten_utils.get_locale_from_db')
    def test_getcurrentlocale(self, mock_get_locale, mock_default_locale):
        mock_get_locale.return_value = 'a_lang'
        mock_default_locale.return_value = [None, 'an_enc']

        test_string = create_test_string(utils.getcurrentlocale())
        reference_string = '[a_lang, an_enc]'
        assert test_string == reference_string
        
@attr(status='only')
class TestGetDelimiter(object):
    def test_get_delimiter_only_one_column(self):
        file = ['obsid',
                 'rb1']

        with utils.tempinput('\n'.join(file), 'utf-8') as filename:
            @mock.patch('midvatten_utils.ask_for_delimiter')
            @mock.patch('qgis.utils.iface', autospec=True)
            def _test(filename, mock_iface, mock_delimiter_question):
                mock_delimiter_question.return_value = (';', True)
                delimiter = utils.get_delimiter(filename, 'utf-8')
                assert delimiter == ';'
            _test(filename)

    def test_get_delimiter_delimiter_not_found(self):
        file = ['obsid;acol,acol2',
                 'rb1;1,2']

        with utils.tempinput('\n'.join(file), 'utf-8') as filename:
            @mock.patch('midvatten_utils.ask_for_delimiter')
            @mock.patch('qgis.utils.iface', autospec=True)
            def _test(filename, mock_iface, mock_delimiter_question):
                mock_delimiter_question.return_value = (',', True)
                delimiter = utils.get_delimiter(filename, 'utf-8')
                assert delimiter == ','
            _test(filename)

    def test_get_delimiter_semicolon(self):
        file = ['obsid;acol;acol2',
                 'rb1;1;2']

        with utils.tempinput('\n'.join(file), 'utf-8') as filename:
            @mock.patch('midvatten_utils.ask_for_delimiter')
            @mock.patch('qgis.utils.iface', autospec=True)
            def _test(filename, mock_iface, mock_delimiter_question):
                mock_delimiter_question.return_value = (';', True)
                delimiter = utils.get_delimiter(filename, 'utf-8')
                assert delimiter == ';'
            _test(filename)

    def test_get_delimiter_comma(self):
        file = ['obsid,acol,acol2',
                 'rb1,1,2']

        with utils.tempinput('\n'.join(file), 'utf-8') as filename:
            @mock.patch('midvatten_utils.ask_for_delimiter')
            @mock.patch('qgis.utils.iface', autospec=True)
            def _test(filename, mock_iface, mock_delimiter_question):
                mock_delimiter_question.return_value = (',', True)
                delimiter = utils.get_delimiter(filename, 'utf-8')
                assert delimiter == ','
            _test(filename)
