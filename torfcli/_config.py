# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details
# http://www.gnu.org/licenses/gpl-3.0.txt

import re
import argparse
import os
import errno

from . import _errors
from . import _vars


class CLIParser(argparse.ArgumentParser):
    def error(self, msg):
        raise _errors.CLIError(msg.capitalize())

_cliparser = CLIParser(add_help=False)

_cliparser.add_argument('PATH', nargs='?')
_cliparser.add_argument('--exclude', '-e', default=[], action='append')
_cliparser.add_argument('--in', '-i', default='')
_cliparser.add_argument('--out', '-o', default='')
_cliparser.add_argument('--name', '-n', default='')
_cliparser.add_argument('--yes', '-y', action='store_true')

_cliparser.add_argument('--magnet', '-m', action='store_true')
_cliparser.add_argument('--tracker', '-t', default=[], action='append')
_cliparser.add_argument('--notracker', '-T', action='store_true')
_cliparser.add_argument('--webseed', '-w', default=[], action='append')
_cliparser.add_argument('--nowebseed', '-W', action='store_true')

_cliparser.add_argument('--private', '-p', action='store_true')
_cliparser.add_argument('--noprivate', '-P', action='store_true')
_cliparser.add_argument('--comment', '-c', default='')
_cliparser.add_argument('--nocomment', '-C', action='store_true')
_cliparser.add_argument('--date', '-d', default='')
_cliparser.add_argument('--nodate', '-D', action='store_true')
_cliparser.add_argument('--xseed', '-x', action='store_true')
_cliparser.add_argument('--noxseed', '-X', action='store_true')
_cliparser.add_argument('--nocreator', '-R', action='store_true')

_cliparser.add_argument('--config', '-f')
_cliparser.add_argument('--noconfig', '-F', action='store_true')
_cliparser.add_argument('--profile', '-z', default=[], action='append')
_cliparser.add_argument('--help', '-h', action='store_true')
_cliparser.add_argument('--version', '-V', action='store_true')

def parse_args(args):
    return vars(_cliparser.parse_args(args))


def get_cfg(cliargs):
    """Combine values from CLI, config file, profiles and defaults"""
    clicfg = parse_args(cliargs)

    # If we don't need to read a config file, return parsed CLI arguments
    cfgfile = clicfg['config'] or _vars.DEFAULT_CONFIG_FILE
    if clicfg['noconfig'] or (not clicfg['config'] and not os.path.exists(cfgfile)):
        return clicfg

    # Read config file
    filecfg = _readfile(cfgfile)

    # Prepend arguments from file to CLI arguments
    args = _cfg2args(filecfg) + cliargs

    # Parse combined arguments from config file and CLI
    try:
        cfg = parse_args(args)
    except _errors.CLIError as e:
        raise _errors.ConfigError(f'{cfgfile}: {e}', errno=e.errno)

    # Apply profiles specified in config file or on CLI
    def apply_profile(profname):
        prof = filecfg.get(profname)
        if prof is None:
            raise _errors.ConfigError(f'{cfgfile}: No such profile: {profname}', errno=errno.EINVAL)
        else:
            profargs.extend(_cfg2args(prof))

    profargs = []
    for profname in cfg['profile']:
        apply_profile(profname)

    # Combine arguments from profiles with arguments from global config and CLI
    args = profargs + args
    try:
        return parse_args(args)
    except _errors.CLIError as e:
        raise _errors.ConfigError(f'{cfgfile}: {e}', errno=e.errno)


_re_bool = re.compile(r'^(\S+)$')
_re_assign = re.compile(r'^(\S+)\s*=\s*(.*)\s*$')

def _readfile(filepath):
    """Read INI-style file into dictionary"""

    # Catch any errors from the OS
    try:
        with open(filepath, 'r') as f:
            lines = tuple(l.strip() for l in f.readlines())
    except OSError as e:
        raise _errors.ConfigError(f'{filepath}: {os.strerror(e.errno)}', errno=e.errno)

    # Parse lines
    cfg = subcfg = {}
    for line in lines:
        # Skip empty lines and comments
        if not line or line[0] == '#':
            continue

        # Start new profile
        if line[0] == '[' and line[-1] == ']':
            profile_name = line[1:-1]
            cfg[profile_name] = subcfg = {}
            continue

        # Boolean option
        bool_match = _re_bool.match(line)
        if bool_match:
            name = bool_match.group(1)
            subcfg[name] = True
            continue

        # Option with a custom value
        assign_match = _re_assign.match(line)
        if assign_match:
            name = assign_match.group(1)
            value = assign_match.group(2).strip()

            # Strip off optional quotes
            if value[0] == value[-1] == '"' or value[0] == value[-1] == "'":
                value = value[1:-1]

            # Multiple occurences of the same name turn its value into a list
            if name in subcfg:
                if not isinstance(subcfg[name], list):
                    subcfg[name] = [subcfg[name]]
                subcfg[name].append(value)
            else:
                subcfg[name] = value

            continue

    return cfg


def _cfg2args(cfg):
    args = []
    for name,value in cfg.items():
        option = '--' + name

        # Option with parameter
        if isinstance(value, str):
            args.extend((option, value))

        # Switch without parameter
        elif isinstance(value, (bool, type(None))):
            args.append(option)

        # Option that can occur multiple times
        elif isinstance(value, list):
            for item in value:
                args.extend((option, item))
    return args


# def _check_circular_reference(filecfg, refs=()):
#     """Ensure profile doesn't reference itself somehow"""
#     for name,value in filecfg.items():
#         if name == 'profile':
#             profile_name = value
#             profile = cfg['profiles'][profile_name]
#             if profile_name in refs:
#                 refs_str = ' -> '.join(refs[1:] + (profile_name,))
#                 raise _errors.CLIError(f'{refs[0]}: Circular reference: {refs_str}')
#             else:
#                 _check_circular_reference(profile, refs=refs + (profile_name,))