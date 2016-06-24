import re

from cassandra import (ConsistencyLevel, InvalidRequest, ReadFailure,
                       ReadTimeout, Unauthorized, Unavailable, WriteFailure,
                       WriteTimeout)
from cassandra.query import SimpleStatement

from tools import rows_to_list

from nose.tools import eq_, assert_false

from time import sleep


def assert_unavailable(fun, *args):
    try:
        if len(args) == 0:
            fun(None)
        else:
            fun(*args)
    except (Unavailable, WriteTimeout, WriteFailure, ReadTimeout, ReadFailure) as e:
        pass
    except Exception as e:
        assert False, "Expecting unavailable exception, got: " + str(e)
    else:
        assert False, "Expecting unavailable exception but no exception was raised"


def assert_invalid(session, query, matching=None, expected=InvalidRequest):
    try:
        res = session.execute(query)
        assert False, "Expecting query to be invalid: got %s" % res
    except AssertionError as e:
        raise e
    except expected as e:
        msg = str(e)
        if matching is not None:
            assert re.search(matching, msg), "Error message does not contain " + matching + " (error = " + msg + ")"


def assert_unauthorized(session, query, message):
    """
    Attempt to issue a query, and assert Unauthorized is raised.
    @param message Expected error message
    @param session Session to use
    @param query Unauthorized query to run
    """
    assert_invalid(session, query, message, Unauthorized)


def assert_one(session, query, expected, cl=ConsistencyLevel.ONE):
    simple_query = SimpleStatement(query, consistency_level=cl)
    res = session.execute(simple_query)
    list_res = rows_to_list(res)
    assert list_res == [expected], "Expected %s from %s, but got %s" % ([expected], query, list_res)


def assert_none(session, query, cl=ConsistencyLevel.ONE):
    simple_query = SimpleStatement(query, consistency_level=cl)
    res = session.execute(simple_query)
    list_res = rows_to_list(res)
    assert list_res == [], "Expected nothing from %s, but got %s" % (query, list_res)


def assert_all(session, query, expected, cl=ConsistencyLevel.ONE, ignore_order=False):
    simple_query = SimpleStatement(query, consistency_level=cl)
    res = session.execute(simple_query)
    list_res = rows_to_list(res)
    if ignore_order:
        expected = sorted(expected)
        list_res = sorted(list_res)
    assert list_res == expected, "Expected %s from %s, but got %s" % (expected, query, list_res)


def assert_almost_equal(*args, **kwargs):
    error = kwargs['error'] if 'error' in kwargs else 0.16
    vmax = max(args)
    vmin = min(args)
    error_message = '' if 'error_message' not in kwargs else kwargs['error_message']
    assert vmin > vmax * (1.0 - error) or vmin == vmax, "values not within %.2f%% of the max: %s (%s)" % (error * 100, args, error_message)


def assert_row_count(session, table_name, expected):
    """ Function to validate the row count expected in table_name """

    query = "SELECT count(*) FROM {};".format(table_name)
    res = session.execute(query)
    count = res[0][0]
    assert count == expected, "Expected a row count of {} in table '{}', but got {}".format(
        expected, table_name, count
    )


def assert_crc_check_chance_equal(session, table, expected, ks="ks", view=False):
    """
    driver still doesn't support top-level crc_check_chance property,
    so let's fetch directly from system_schema
    """
    if view:
        assert_one(session,
                   "SELECT crc_check_chance from system_schema.views WHERE keyspace_name = 'ks' AND "
                   "view_name = '{table}';".format(table=table),
                   [expected])
    else:
        assert_one(session,
                   "SELECT crc_check_chance from system_schema.tables WHERE keyspace_name = 'ks' AND "
                   "table_name = '{table}';".format(table=table),
                   [expected])


def assert_bootstrap_state(exclusive_session, state):
    rows = exclusive_session.execute("SELECT bootstrapped FROM system.local WHERE key='local'")
    eq_(rows[0][0], state)


def assert_not_running(node):
    attempts = 0
    while node.is_running() and attempts < 10:
        sleep(1)
        attempts = attempts + 1

    assert_false(node.is_running())
