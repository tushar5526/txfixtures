# Copyright 2009-2011 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for txfixtures.tachandler"""

__metaclass__ = type

from os.path import (
    dirname,
    exists,
    join,
    )
import subprocess
import warnings

from fixtures import TempDir
import testtools
from testtools.matchers import (
    Matcher,
    Mismatch,
    Not,
    )

from ..tachandler import (
    TacException,
    TacTestSetup,
    )
from ..osutils import (
    get_pid_from_file,
    )


class SimpleTac(TacTestSetup):

    def __init__(self, name, tempdir, port):
        super(SimpleTac, self).__init__()
        self.name, self.tempdir = name, tempdir
        self.port = port

    @property
    def root(self):
        return dirname(__file__)

    @property
    def tacfile(self):
        return join(self.root, '%s.tac' % self.name)

    @property
    def pidfile(self):
        return join(self.tempdir, '%s.pid' % self.name)

    @property
    def logfile(self):
        return join(self.tempdir, '%s.log' % self.name)

    @property
    def daemon_port(self):
        return self.port

    def setUpRoot(self):
        pass


class IsRunning(Matcher):
    """Ensures the `TacTestSetup`'s process is running."""

    def match(self, fixture):
        pid = get_pid_from_file(fixture.pidfile)
        if pid is None or not exists("/proc/%d" % pid):
            return Mismatch("Fixture %r is not running." % fixture)

    def __str__(self):
        return self.__class__.__name__


class TacTestSetupTestCase(testtools.TestCase):
    """Some tests for the error handling of TacTestSetup."""

    def test_okay(self):
        """TacTestSetup sets up and runs a simple service."""
        tempdir = self.useFixture(TempDir()).path
        fixture = SimpleTac("okay", tempdir, 9876)

        # Fire up the fixture, capturing warnings.
        with warnings.catch_warnings(record=True) as warnings_log:
            with fixture:
                self.assertThat(fixture, IsRunning())
            self.assertThat(fixture, Not(IsRunning()))

        # No warnings are emitted.
        self.assertEqual([], warnings_log)

    def test_missingTac(self):
        """TacTestSetup raises TacException if the tacfile doesn't exist"""
        fixture = SimpleTac("missing", "/file/does/not/exist", 0)
        try:
            self.assertRaises(TacException, fixture.setUp)
            self.assertThat(fixture, Not(IsRunning()))
        finally:
            fixture.cleanUp()

    def test_couldNotListenTac(self):
        """If the tac fails due to not being able to listen on the needed
        port, TacTestSetup will fail.
        """
        tempdir = self.useFixture(TempDir()).path
        fixture = SimpleTac("cannotlisten", tempdir, 1)
        try:
            self.assertRaises(TacException, fixture.setUp)
            self.assertThat(fixture, Not(IsRunning()))
        finally:
            fixture.cleanUp()

    def test_stalePidFile(self):
        """TacTestSetup complains about stale pid files."""
        tempdir = self.useFixture(TempDir()).path
        fixture = SimpleTac("okay", tempdir, 9876)

        # Run a short-lived process with the intention of using its pid in the
        # next step. Linux uses pids sequentially (from the information I've
        # been able to discover) so this approach is safe as long as we don't
        # delay until pids wrap... which should be a very long time unless the
        # machine is seriously busy.
        process = subprocess.Popen("true")
        process.wait()

        # Put the (now bogus) pid in the pid file.
        with open(fixture.pidfile, "wb") as pidfile:
            pidfile.write(str(process.pid))

        # Fire up the fixture, capturing warnings.
        with warnings.catch_warnings(record=True) as warnings_log:
            try:
                self.assertRaises(TacException, fixture.setUp)
                self.assertThat(fixture, Not(IsRunning()))
            finally:
                fixture.cleanUp()

        # One deprecation warning is emitted.
        self.assertEqual(1, len(warnings_log))
        self.assertIs(UserWarning, warnings_log[0].category)
