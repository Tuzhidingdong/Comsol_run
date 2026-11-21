from __future__ import annotations

from comsol_agent.process_manager import _job_process_ids


class FakeWin32Job:
    def __init__(self, value):
        self.value = value

    def QueryInformationJobObject(self, job, info_class):
        return self.value


def test_job_object_pid_decoder_accepts_documented_pywin32_pid_tuple():
    assert _job_process_ids(FakeWin32Job((101, 202)), object()) == [101, 202]


def test_job_object_pid_decoder_accepts_process_id_list_dictionary():
    assert _job_process_ids(
        FakeWin32Job({"ProcessIdList": (303, 404)}),
        object()
    ) == [303, 404]


def test_job_object_pid_decoder_accepts_legacy_wrapped_sequence():
    assert _job_process_ids(FakeWin32Job((2, 2, (505, 606))), object()) == [505, 606]


def test_job_object_pid_decoder_fails_closed_on_unrecognized_shape():
    assert _job_process_ids(FakeWin32Job("unexpected"), object()) == []
