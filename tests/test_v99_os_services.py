import pytest

from v99.os.services import (
    BUNDLE_DIR,
    INSTALL_STATUS,
    validate_bundle,
    validate_launchd_plist,
    validate_systemd_unit,
    validate_windows_task,
    REQUIRED_SERVICE_KEYS,
    REQUIRED_TIMER_KEYS,
)


def _unit_text(section: str, key: str, value: str, **overrides):
    base = {
        'Unit': '[Unit]\nDescription=V91 test\n',
        'Service': '[Service]\nType=oneshot\nExecStart=/usr/bin/true\nNoNewPrivileges=true\nProtectSystem=strict\nPrivateTmp=true\n',
        'Install': '[Install]\nWantedBy=multi-user.target\n',
        'Timer': '[Timer]\nOnCalendar=*:0/15\nUnit=v91-cycle.service\n',
    }
    base[dict(section=section).get('section', section)] = base[section].replace(f'{key}=', f'{key}=')
    return base


GOOD_SERVICE = '''[Unit]
Description=V91

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 main.py
NoNewPrivileges=true
ProtectSystem=strict
PrivateTmp=true

[Install]
WantedBy=multi-user.target
'''

GOOD_TIMER = '''[Unit]
Description=V91 timer

[Timer]
OnCalendar=*:0/15
Unit=v91-cycle.service

[Install]
WantedBy=timers.target
'''


def test_valid_service_unit_passes():
    assert validate_systemd_unit(GOOD_SERVICE, REQUIRED_SERVICE_KEYS) == []


def test_valid_timer_passes():
    assert validate_systemd_unit(GOOD_TIMER, REQUIRED_TIMER_KEYS) == []


def test_service_with_hardening_disabled_fails():
    text = GOOD_SERVICE.replace('NoNewPrivileges=true', 'NoNewPrivileges=false')
    errors = validate_systemd_unit(text, REQUIRED_SERVICE_KEYS)
    assert any('NoNewPrivileges' in e for e in errors)


def test_service_with_weak_protect_system_fails():
    text = GOOD_SERVICE.replace('ProtectSystem=strict', 'ProtectSystem=full')
    errors = validate_systemd_unit(text, REQUIRED_SERVICE_KEYS)
    assert any('ProtectSystem' in e for e in errors)


def test_service_missing_execstart_fails():
    text = GOOD_SERVICE.replace('ExecStart=/usr/bin/python3 main.py\n', '')
    errors = validate_systemd_unit(text, REQUIRED_SERVICE_KEYS)
    assert any('ExecStart' in e for e in errors)


def test_empty_unit_fails():
    assert validate_systemd_unit('', REQUIRED_SERVICE_KEYS) != []


def test_valid_plist_passes():
    plist = (BUNDLE_DIR / 'launchd/com.v91.cycle.plist').read_text(encoding='utf-8')
    assert validate_launchd_plist(plist) == []


def test_plist_with_missing_label_fails():
    text = '<plist version="1.0"><dict><key>StartInterval</key><integer>900</integer></dict></plist>'
    errors = validate_launchd_plist(text)
    assert any('Label' in e for e in errors)


def test_plist_with_tight_interval_fails():
    text = ('<plist version="1.0"><dict><key>Label</key><string>x</string>'
            '<key>ProgramArguments</key><array><string>/usr/bin/true</string></array>'
            '<key>StartInterval</key><integer>10</integer></dict></plist>')
    errors = validate_launchd_plist(text)
    assert any('60 seconds' in e for e in errors)


def test_windows_task_passes():
    xml = (BUNDLE_DIR / 'windows/V91-Cycle-Task.xml').read_text(encoding='utf-8')
    assert validate_windows_task(xml) == []


def test_windows_task_without_repetition_fails():
    text = ('<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
            '<Triggers><TimeTrigger><Enabled>true</Enabled></TimeTrigger></Triggers>'
            '<Actions><Exec><Command>python</Command></Exec></Actions></Task>')
    errors = validate_windows_task(text)
    assert any('Repetition' in e for e in errors)


def test_bundle_validates_all_shipped_files():
    result = validate_bundle()
    assert result['bundle_validation'] == 'ALL_FILES_VALID', result['files']
    assert result['install_status'] == INSTALL_STATUS
    assert INSTALL_STATUS.endswith('NOT_INSTALLED')


def test_bundle_files_exist():
    for relative in ('systemd/v91-cycle.service', 'systemd/v91-cycle.timer',
                     'launchd/com.v91.cycle.plist', 'windows/V91-Cycle-Task.xml'):
        assert (BUNDLE_DIR / relative).is_file(), relative
