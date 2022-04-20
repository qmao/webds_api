import pytest
from testBridge import TestBridge

def pytest_report_teststatus(report, config):
    if report.when == 'call':
        TestBridge().setTestResult(report.nodeid, 'done', report.outcome)


def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing collection and entering the run test loop.
    """
    print("start session: ", session)

def pytest_sessionfinish(session, exitstatus):
    TestBridge().setTestResult(None, 'finished', None)

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    ###print('called before running item ', item.nodeid)
    TestBridge().setTestResult(item.nodeid, 'started', None)
    yield

##@pytest.mark.hookwrapper
##@pytest.mark.tryfirst
##def pytest_runtest_call(item):
##    yield