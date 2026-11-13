"""Process ownership/card isolation failures, with no game or shell launch."""
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import private_process_checks as checks


class Gone(Exception):
    pass


class Denied(Exception):
    pass


def fake_process(pid=23, name="Einhander_Recompiled.exe", executable="C:/private/runtime/Einhander_Recompiled.exe", command=None):
    process = Mock(pid=pid)
    process.name.return_value = name
    process.exe.return_value = executable
    process.cmdline.return_value = command or [executable, "--debug-port", "4376"]
    process.create_time.return_value = 100
    process.is_running.return_value = True
    return process


class ProcessChecksTests(unittest.TestCase):
    def setUp(self):
        self.process = fake_process()
        self.api = SimpleNamespace(Process=Mock(return_value=self.process),
            process_iter=Mock(return_value=[self.process]), NoSuchProcess=Gone)
        self.names = patch.object(checks, "_process_names", return_value=[(23, "Einhander_Recompiled.exe")]).start()
        self.addCleanup(patch.stopall)

    def test_identity_has_pid_executable_and_complete_argument_vector(self):
        row = checks._inspect(23, self.api)
        self.assertEqual(23, row["ProcessId"])
        self.assertEqual(self.process.exe(), row["ExecutablePath"])
        self.assertEqual(self.process.cmdline(), row["CommandLine"])

    def test_missing_or_changed_identity_refuses(self):
        for method, value in [("exe", ""), ("cmdline", []), ("name", ""), ("is_running", False)]:
            with self.subTest(method=method):
                process = fake_process()
                getattr(process, method).return_value = value
                self.api.Process.return_value = process
                with self.assertRaises(RuntimeError):
                    checks._inspect(23, self.api)
        self.api.Process.return_value = fake_process()
        self.api.Process.return_value.create_time.side_effect = [100, 101]
        with self.assertRaisesRegex(RuntimeError, "changed"):
            checks._inspect(23, self.api)

    def test_invalid_pid_refuses(self):
        for value in [0, -1, True, "23"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                checks._inspect(value, self.api)

    def test_missing_target_and_access_denied_do_not_become_identity_success(self):
        for error in [Gone(), Denied()]:
            self.api.Process.side_effect = error
            with self.assertRaises(type(error)):
                checks._inspect(23, self.api)

    def test_inventory_does_not_read_unrelated_command_lines(self):
        unrelated = fake_process(pid=24, name="another-app.exe")
        self.names.return_value = [(24, "another-app.exe"), (23, "Einhander_Recompiled.exe")]
        self.assertEqual(1, len(checks._game_processes(self.api)))
        unrelated.exe.assert_not_called()
        unrelated.cmdline.assert_not_called()

    def test_inventory_access_denied_fails_closed_and_disappeared_process_is_absent(self):
        self.api.Process.side_effect = Denied()
        with self.assertRaises(Denied):
            checks._game_processes(self.api)
        self.api.Process.side_effect = Gone()
        self.assertEqual([], checks._game_processes(self.api))

    def test_inventory_unknown_name_and_failed_snapshot_refuse(self):
        self.names.return_value = [(236, "")]
        with self.assertRaisesRegex(RuntimeError, "Unknown"):
            checks._game_processes(self.api)
        self.names.side_effect = OSError("snapshot failed")
        with self.assertRaises(OSError):
            checks._game_processes(self.api)

    def test_inventory_deadline_refuses_partial_result(self):
        clock = Mock(side_effect=[1, 5])
        with self.assertRaises(TimeoutError):
            checks._game_processes(self.api, seconds=3, clock=clock)

    def test_query_uses_bounded_python_child_without_shell(self):
        result = SimpleNamespace(stdout=json.dumps({"ProcessId": 23}))
        with patch.object(checks.subprocess, "run", return_value=result) as run:
            checks.process_identity(23)
        args, kwargs = run.call_args
        self.assertEqual(checks.sys.executable, args[0][0])
        self.assertEqual(["identity", "23"], args[0][-2:])
        self.assertEqual(5, kwargs["timeout"])
        self.assertTrue(kwargs["check"])
        self.assertNotIn("shell", kwargs)

    def test_timeout_failed_query_and_malformed_json_fail_closed(self):
        for error in [subprocess.TimeoutExpired("query", 5), subprocess.CalledProcessError(1, "query"), OSError("unavailable")]:
            with self.subTest(error=type(error).__name__), patch.object(checks.subprocess, "run", side_effect=error):
                with self.assertRaises(RuntimeError):
                    checks.running_games()
        with patch.object(checks.subprocess, "run", return_value=SimpleNamespace(stdout="not json")):
            with self.assertRaises(RuntimeError):
                checks.running_games()

    def test_wrong_pid_and_inventory_schema_fail_closed(self):
        with patch.object(checks, "_query", return_value={"ProcessId": 99}):
            with self.assertRaises(RuntimeError):
                checks.process_identity(23)
        with patch.object(checks, "_query", return_value={}):
            with self.assertRaises(RuntimeError):
                checks.running_games()

    def test_private_ownership_requires_pid_exe_directory_and_same_argv(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            executable = directory / "runtime" / "game.exe"
            argv = [str(executable), "--debug-port", "4376"]
            row = dict(ProcessId=23, ExecutablePath=str(executable), CommandLine=argv)
            checks.verify_private_identity(row, 23, argv, directory)
            for bad in [dict(row, ProcessId=24), dict(row, ExecutablePath=str(directory / "wrong.exe")),
                        dict(row, CommandLine=[]), dict(row, CommandLine=[str(executable), "--debug-port", "9999"])]:
                with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                    checks.verify_private_identity(bad, 23, argv, directory)
            with self.assertRaisesRegex(RuntimeError, "escaped"):
                checks.verify_private_identity(row, 23, argv, directory / "elsewhere")

    def test_seed_usage_is_caught_with_forward_or_back_slashes_and_in_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "closed-private-seed"
            for referenced in [str(source), str(source).replace("\\", "/"), str(source).replace("/", "\\").upper()]:
                row = dict(ExecutablePath="C:/another/game.exe", CommandLine=["C:/another/game.exe", "--memcard-dir", referenced])
                with self.subTest(referenced=referenced), self.assertRaisesRegex(RuntimeError, "active use"):
                    checks.require_seed_closed([row], source)
            checks.require_seed_closed([], source)
            checks.require_seed_closed([dict(ExecutablePath="C:/another/game.exe", CommandLine=["C:/another/game.exe"])], source)
            for row in [{}, dict(ExecutablePath="C:/game.exe", CommandLine=[])]:
                with self.assertRaisesRegex(RuntimeError, "unknown"):
                    checks.require_seed_closed([row], source)


class CaptureIntegrationTests(unittest.TestCase):
    def test_launch_receipt_identity_checks_real_argument_vector_before_input(self):
        import run_facade_ab_probe as probe
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            argv = [str(directory / "runtime" / "game.exe"), "--debug-port", "4376"]
            launch = dict(pid=23)
            (directory / "launch-candidate.json").write_text(json.dumps(launch))
            report = dict(evidence=str(directory), launches=dict(candidate=dict(arguments=argv)))
            row = dict(ProcessId=23, ExecutablePath=argv[0], CommandLine=argv)
            with patch.object(probe, "process_identity", return_value=row):
                self.assertEqual(launch, probe.identity(report))
            with patch.object(probe, "process_identity", return_value=dict(row, CommandLine=[*argv[:-1], "9999"])):
                with self.assertRaisesRegex(RuntimeError, "command line"):
                    probe.identity(report)

    def test_native_menu_preparation_selects_scale2_reference(self):
        import run_stage1_pacing_ab as pacing
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "source" / "runtime" / "game.exe"
            original.parent.mkdir(parents=True)
            original.write_bytes(b"private fake runtime")
            (original.parent / "cache").mkdir()
            (original.parent / "settings.toml").write_text(
                "supersampling = 9\nrewind_depth = 0\nrewind_interval = 15\nhd_textures = true\n"
                'hd_texture_root = "old"\ndir = "old"\ncard1 = "old"\ncard2 = "old"\n')
            seed = root / "closed-card.mcd"
            seed.write_bytes(b"private card")
            source = root / "candidate.json"
            source.write_text(json.dumps(dict(launches=dict(candidate=dict(
                arguments=[str(original), "--debug-port", "4376", "--memcard-dir", "old", "--window-title", "test"],
                executable_sha256=pacing.ui.sha(original),
                environment_overrides=dict(PSXRECOMP_HD_TEXTURE_ROOT=str(root / "pack")))))))
            for scale, profile in [(2, "native-stock-scale2"), (9, "native-stock")]:
                args = SimpleNamespace(batch="scale"+str(scale), candidate=source, runtime=None,
                    supersampling=scale, gpu_queries=0, world_sampling=0, guest_frames=0, native_menus=True)
                with patch.object(pacing, "ROOT", root / "prepared"), patch.object(pacing.world, "closed_private_seed", return_value=(seed, {})):
                    report = pacing.prepare("hd-on_rewind-off", args)
                self.assertEqual(profile, report["route_reference_profile"])
                self.assertEqual("0\n", (Path(report["evidence"]) / "replacement-control.txt").read_text())


if __name__ == "__main__":
    unittest.main()
