from torfcli import run
from torfcli import _errors as err
from torfcli import _vars

import pytest
from unittest.mock import patch
import json
import time
import io
import sys


def test_json_contains_standard_fields(capsys, mock_content):
    now = time.time()
    run([str(mock_content), '--json'])
    cap = capsys.readouterr()
    j = json.loads(cap.out)
    assert isinstance(j['Name'], str)
    assert isinstance(j['Size'], int)
    assert j['Created'] == pytest.approx(now - 1, abs=2)
    assert j['Created By'] == f'{_vars.__appname__} {_vars.__version__}'
    assert isinstance(j['Private'], bool)
    assert isinstance(j['Piece Size'], int)
    assert isinstance(j['Piece Count'], int)
    assert isinstance(j['File Count'], int)
    assert isinstance(j['Files'], list)
    for f in j['Files']:
        assert isinstance(f, str)
    assert isinstance(j['Info Hash'], str)
    assert len(j['Info Hash']) == 40
    assert j['Magnet'].startswith('magnet:?xt=urn:btih:')
    assert isinstance(j['Torrent'], str)

def test_json_does_not_contain_progress(capsys, mock_content):
    now = time.time()
    run([str(mock_content), '--json'])
    cap = capsys.readouterr()
    assert cap.err == ''
    j = json.loads(cap.out)
    assert 'Progress' not in j

def test_json_contains_cli_errors(capsys):
    with patch('sys.exit') as mock_exit:
        run(['--foo', '--json'])
    mock_exit.assert_called_once_with(err.Code.CLI)
    cap = capsys.readouterr()
    assert cap.err == ''
    j = json.loads(cap.out)
    assert j['Error'] == ['Unrecognized arguments: --foo']

def test_json_contains_config_errors(capsys, cfgfile):
    cfgfile.write('''
    foo
    ''')
    with patch('sys.exit') as mock_exit:
        run(['--json'])
    mock_exit.assert_called_once_with(err.Code.CONFIG)
    cap = capsys.readouterr()
    assert cap.err == ''
    j = json.loads(cap.out)
    assert j['Error'] == [f'{cfgfile}: Unrecognized arguments: --foo']

def test_json_contains_regular_errors(capsys):
    with patch('sys.exit') as mock_exit:
        run(['-i', 'path/to/nonexisting.torrent', '--json'])
    mock_exit.assert_called_once_with(err.Code.READ)
    cap = capsys.readouterr()
    assert cap.err == ''
    j = json.loads(cap.out)
    assert j['Error'] == ['path/to/nonexisting.torrent: No such file or directory']

def test_json_contains_sigint(capsys, mock_create_mode, mock_content):
    mock_create_mode.side_effect = KeyboardInterrupt()
    with patch('sys.exit') as mock_exit:
        run([str(mock_content), '--json'])
    mock_exit.assert_called_once_with(err.Code.ABORTED)
    cap = capsys.readouterr()
    assert cap.err == ''
    j = json.loads(cap.out)
    assert j['Error'] == ['Aborted']

def test_json_contains_verification_errors(capsys, tmp_path, create_torrent):
    content_path = tmp_path / 'file.jpg'
    content_path.write_text('some data')

    with create_torrent(path=content_path) as torrent_file:
        content_path.write_text('some data!!!')
        with patch('sys.exit') as mock_exit:
            run([str(content_path), '-i', torrent_file, '--json'])
    mock_exit.assert_called_once_with(err.Code.VERIFY)
    cap = capsys.readouterr()
    assert cap.err == ''
    j = json.loads(cap.out)
    assert j['Error'] == [f'{content_path}: Too big: 12 instead of 9 bytes',
                          f'{content_path} does not satisfy {torrent_file}']