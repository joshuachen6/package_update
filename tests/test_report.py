from shared.report import _task_status, skipped_reason_status


def test_gradle_not_present_reason_is_skipped_not_could_not_update():
    status = _task_status(
        101,
        set(),
        {101: ["not applicable"]},
    )
    assert status == "Skipped"


def test_gradle_transitive_not_found_reason_is_skipped_not_could_not_update():
    status = _task_status(
        101,
        set(),
        {101: ["transitive dep not found in dependency tree"]},
    )
    assert status == "Skipped"


def test_gradle_no_same_major_fallback_reason_is_skipped_not_could_not_update():
    status = _task_status(
        101,
        set(),
        {101: ["no fixed versions for current major and no accessible same-major update found"]},
    )
    assert status == "Skipped"


def test_real_update_failure_stays_could_not_update():
    status = _task_status(
        101,
        set(),
        {101: ["no accessible version found >= target"]},
    )
    assert status == "Could not update"


def test_completed_wins_over_skipped_reasons():
    status = _task_status(
        101,
        {101},
        {101: ["not applicable"]},
    )
    assert status == "Completed"


def test_skipped_reason_status_marks_real_update_failure():
    assert skipped_reason_status("no accessible version found >= target") == "Could not update"


def test_skipped_reason_status_marks_non_applicable_as_skipped():
    assert skipped_reason_status("not applicable") == "Skipped"


def test_skipped_reason_status_marks_already_compliant_as_resolved():
    assert skipped_reason_status("current version already meets remediation target") == "Resolved"
