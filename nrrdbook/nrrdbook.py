#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nrrdbook
Version:  0.0.2
Author:   Sean O'Connell <sean@sdoconnell.net>
License:  MIT
Homepage: https://github.com/sdoconnell/nrrdbook
About:
A terminal-based address book with mutt/neomutt integration and local
file-based contact storage.

usage: nrrdbook [-h] [-c <file>] for more help: nrrdbook <command> -h ...

Terminal-based address book for nerds.

commands:
  (for more help: nrrdbook <command> -h)
    delete (rm)         delete contact
    edit                edit a contact file (uses $EDITOR)
    export              search and output in vCard 4.0 format
    info                show details about a contact
    list (ls)           list contacts
    modify (mod)        modify a contact
    mutt                output for mutt query
    new                 create a new contact
    notes               add/update notes on a contact (uses $EDITOR)
    query               search contacts with structured text output
    search              search contacts
    shell               interactive shell
    unset               clear a field from a specified contact
    version             show version info

optional arguments:
  -h, --help            show this help message and exit
  -c <file>, --config <file>
                        config file


Copyright © 2021 Sean O'Connell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import argparse
import base64
import configparser
import json
import os
import random
import re
import string
import subprocess
import sys
import tempfile
import time
import uuid
from cmd import Cmd
from datetime import datetime, timezone
from email.parser import HeaderParser
from textwrap import TextWrapper

import tzlocal
import yaml
from dateutil import parser as dtparser
from rich import box
from rich.color import ColorParseError
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

APP_NAME = "nrrdbook"
APP_VERS = "0.0.2"
APP_COPYRIGHT = "Copyright © 2021 Sean O'Connell."
APP_LICENSE = "Released under MIT license."
DEFAULT_DATA_DIR = f"$HOME/.local/share/{APP_NAME}"
DEFAULT_CONFIG_FILE = f"$HOME/.config/{APP_NAME}/config"
DEFAULT_CONFIG = (
    "[main]\n"
    f"data_dir = {DEFAULT_DATA_DIR}\n"
    "\n"
    "[colors]\n"
    "disable_colors = false\n"
    "disable_bold = false\n"
    "# set to 'true' if your terminal pager supports color\n"
    "# output and you would like color output when using\n"
    "# the '--pager' ('-p') option\n"
    "color_pager = false\n"
    "# custom colors\n"
    "#info_header = green\n"
    "#info_subheader = bright_magenta\n"
    "#info_label = blue\n"
    "#info_field = red\n"
    "#info_section = white\n"
    "#info_primary = cyan\n"
    "#list_title = bright_blue\n"
    "#list_header = red\n"
    "#list_alias = bright_yellow\n"
    "#list_name = bright_white\n"
    "#list_email = bright_blue\n"
    "#list_phone = bright_magenta\n"
    "#list_tags = bright_cyan\n"
)


class Contacts():
    """Performs address book operations.

    Attributes:
        config_file (str):  application config file.
        data_dir (str):     directory containing address book entries.
        dflt_config (str):  the default config if none is present.

    """
    def __init__(
            self,
            config_file,
            data_dir,
            dflt_config):
        """Initializes a Contacts() object."""
        self.config_file = config_file
        self.data_dir = data_dir
        self.config_dir = os.path.dirname(self.config_file)
        self.dflt_config = dflt_config
        self.interactive = False

        # editor (required for some functions)
        self.editor = os.environ.get("EDITOR")

        # default colors
        self.color_infoheader = "yellow"
        self.color_infosubheader = "bright_white"
        self.color_infolabel = "bright_black"
        self.color_infofield = "default"
        self.color_infosection = "blue"
        self.color_infoprimary = "yellow"
        self.color_listtitle = "bright_blue"
        self.color_listheader = "magenta"
        self.color_listalias = "yellow"
        self.color_listname = "default"
        self.color_listemail = "green"
        self.color_listphone = "blue"
        self.color_listtags = "cyan"
        self.color_bold = True

        # initial definitions, these are updated after the config
        # file is parsed for custom colors
        self.style_infoheader = None
        self.style_infosubheader = None
        self.style_infolabel = None
        self.style_infofield = None
        self.style_infosection = None
        self.style_listtitle = None
        self.style_listheader = None
        self.style_listalias = None
        self.style_listname = None
        self.style_listemail = None
        self.style_listphone = None
        self.style_listtags = None

        # defaults
        self.ltz = tzlocal.get_localzone()
        self.add_emails = None
        self.add_phones = None
        self.add_addresses = None
        self.add_messaging = None
        self.add_websites = None
        self.add_pgpkeys = None

        self._default_config()
        self._parse_config()
        self._verify_data_dir()
        self._parse_files()

    def _alias_not_found(self, alias):
        """Report an invalid alias and exit or pass appropriately.
        Args:
            alias (str):    the invalid alias.
        """
        self._handle_error(f"Alias '{alias}' not found")

    def _datetime_or_none(self, timestr):
        """Verify a datetime object or a datetime string in ISO format
        and return a datetime object or None.
        Args:
            timestr (str): a datetime formatted string.
        Returns:
            timeobj (datetime): a valid datetime object or None.
        """
        if isinstance(timestr, datetime):
            timeobj = timestr.astimezone(tz=self.ltz)
        else:
            try:
                timeobj = dtparser.parse(timestr).astimezone(tz=self.ltz)
            except (TypeError, ValueError, dtparser.ParserError):
                timeobj = None
        return timeobj

    def _default_config(self):
        """Create a default configuration directory and file if they
        do not already exist.

        """
        if not os.path.exists(self.config_file):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
                with open(self.config_file, "w",
                          encoding="utf-8") as config_file:
                    config_file.write(self.dflt_config)
            except IOError:
                self._error_exit(
                    "Config file doesn't exist "
                    "and can't be created.")

    @staticmethod
    def _error_exit(errormsg):
        """Print an error message and exit with a status of 1

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')
        sys.exit(1)

    @staticmethod
    def _error_pass(errormsg):
        """Print an error message but don't exit.

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')

    @staticmethod
    def _format_timestamp(timeobj, pretty=False):
        """Convert a datetime obj to a string.

        Args:
            timeobj (datetime): a datetime object.
            pretty (bool):      return a pretty formatted string.

        Returns:
            timestamp (str): "%Y-%m-%d %H:%M:%S" or "%Y-%m-%d[ %H:%M]".

        """
        if pretty:
            if timeobj.strftime("%H:%M") == "00:00":
                timestamp = timeobj.strftime("%Y-%m-%d")
            else:
                timestamp = timeobj.strftime("%Y-%m-%d %H:%M")
        else:
            timestamp = timeobj.strftime("%Y-%m-%d %H:%M:%S")
        return timestamp

    def _gen_alias(self):
        """Generates a new alias and check for collisions.

        Returns:
            alias (str):    a randomly-generated alias.

        """
        aliases = self._get_aliases()
        chars = string.ascii_lowercase + string.digits
        while True:
            alias = ''.join(random.choice(chars) for x in range(4))
            if alias not in aliases:
                break
        return alias

    def _get_aliases(self):
        """Generates a list of all contact aliases.

        Returns:
            aliases (list): the list of all contact aliases.

        """
        aliases = []
        for contact in self.contacts:
            alias = self.contacts[contact].get('alias')
            if alias:
                aliases.append(alias.lower())
        return aliases

    def _handle_error(self, msg):
        """Reports an error message and conditionally handles error exit
        or notification.

        Args:
            msg (str):  the error message.

        """
        if self.interactive:
            self._error_pass(msg)
        else:
            self._error_exit(msg)

    @staticmethod
    def _lowered_or_none(inputstr):
        """Returns a lowercase string if input is a string or None if
        input is None.

        Args:
            inputstr (str or None):   the input string to lowercase.

        Returns:
            lowered (str or None):    the converted string or None.

        """
        if inputstr:
            try:
                lowered = inputstr.lower()
            except (TypeError, ValueError, AttributeError):
                lowered = None
        else:
            lowered = None
        return lowered

    def _parse_address(self, address):
        """Parses an address statement and returns structured data.

        Args:
            address (str):  the address option provided.

        Returns:
            data (dict):    the parsed address data.

        """
        if len(address) == 3:
            description = address[0]
            field = address[1]
            primary = address[2].lower() == "primary"
        elif len(address) == 2:
            description = address[0]
            field = address[1]
            primary = False
        else:
            description = "address"
            field = address[0]
            primary = False

        field = field.split(';')
        if len(field) < 6:
            self._error_pass(
                "invalid address format "
                "('address1;address2;city;state;zipcode;country')")
            data = None
        else:
            address1 = field[0]
            address2 = field[1]
            city = field[2]
            state = field[3]
            zipcode = field[4]
            country = field[5]

            data = {
                    "address1": address1,
                    "address2": address2,
                    "city": city,
                    "state": state,
                    "zipcode": zipcode,
                    "country": country,
                    "description": description
            }
            if primary:
                data["primary"] = True
        return data

    def _parse_config(self):
        """Read and parse the configuration file."""
        config = configparser.ConfigParser()
        if os.path.isfile(self.config_file):
            try:
                config.read(self.config_file)
            except configparser.Error:
                self._error_exit("Error reading config file")

            if "main" in config:
                if config["main"].get("data_dir"):
                    self.data_dir = os.path.expandvars(
                        os.path.expanduser(
                            config["main"].get("data_dir")))

            def _apply_colors():
                """Try to apply custom colors and catch exceptions for
                invalid color names.

                """
                try:
                    self.style_infoheader = Style(
                        color=self.color_infoheader,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_infosubheader = Style(
                        color=self.color_infosubheader,
                        bold=False)
                except ColorParseError:
                    pass
                try:
                    self.style_infolabel = Style(
                        color=self.color_infolabel,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_infofield = Style(
                        color=self.color_infofield,
                        bold=False)
                except ColorParseError:
                    pass
                try:
                    self.style_infosection = Style(
                        color=self.color_infosection,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_listtitle = Style(
                        color=self.color_listtitle,
                        bold=self.color_bold,
                        italic=False)
                except ColorParseError:
                    pass
                try:
                    self.style_listheader = Style(
                        color=self.color_listheader,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_listalias = Style(
                        color=self.color_listalias,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_listname = Style(
                        color=self.color_listname,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_listemail = Style(
                        color=self.color_listemail,
                        bold=False)
                except ColorParseError:
                    pass
                try:
                    self.style_listphone = Style(
                        color=self.color_listphone,
                        bold=False)
                except ColorParseError:
                    pass
                try:
                    self.style_listtags = Style(
                        color=self.color_listtags,
                        bold=False)
                except ColorParseError:
                    pass

            # apply default colors
            _apply_colors()

            if "colors" in config:
                # custom colors
                self.color_infoheader = (
                    config["colors"].get(
                        "info_header", "bright_yellow"))
                self.color_infosubheader = (
                    config["colors"].get(
                        "info_subheader", "bright_white"))
                self.color_infolabel = (
                    config["colors"].get(
                        "info_label", "bright_black"))
                self.color_infofield = (
                    config["colors"].get(
                        "info_field", "default"))
                self.color_infosection = (
                    config["colors"].get(
                        "info_section", "blue"))
                self.color_infoprimary = (
                    config["colors"].get(
                        "info_primary", "yellow"))
                self.color_listtitle = (
                    config["colors"].get(
                        "list_title", "bright_blue"))
                self.color_listheader = (
                    config["colors"].get(
                        "list_header", "magenta"))
                self.color_listalias = (
                    config["colors"].get(
                        "list_alias", "yellow"))
                self.color_listname = (
                    config["colors"].get(
                        "list_name", "default"))
                self.color_listemail = (
                    config["colors"].get(
                        "list_email", "green"))
                self.color_listphone = (
                    config["colors"].get(
                        "list_phone", "blue"))
                self.color_listtags = (
                    config["colors"].get(
                        "list_tags", "cyan"))

                # disable colors
                if bool(config["colors"].getboolean("disable_colors")):
                    self.color_infoheader = "default"
                    self.color_infosubheader = "default"
                    self.color_infolabel = "default"
                    self.color_infofield = "default"
                    self.color_infosection = "default"
                    self.color_infoprimary = "default"
                    self.color_listtitle = "default"
                    self.color_listheader = "default"
                    self.color_listalias = "default"
                    self.color_listname = "default"
                    self.color_listemail = "default"
                    self.color_listphone = "default"
                    self.color_listtags = "default"

                # disable bold
                if bool(config["colors"].getboolean("disable_bold")):
                    self.color_bold = False

                # color paging (disabled by default)
                self.color_pager = config["colors"].getboolean(
                    "color_pager", "False")

                # try to apply requested custom colors
                _apply_colors()
        else:
            self._error_exit("Config file not found")

    def _parse_contact(self, uid):
        """Parse a contact and return values for contact parameters.

        Args:
            uid (str): the UUID of the contact to parse.

        Returns:
            contact (dict): the contact parameters.

        """
        contact = {}
        contact['uid'] = self.contacts[uid].get('uid')

        contact['created'] = self.contacts[uid].get('created')
        if contact['created']:
            contact['created'] = self._datetime_or_none(
                    contact['created'])

        contact['updated'] = self.contacts[uid].get('updated')
        if contact['updated']:
            contact['updated'] = self._datetime_or_none(
                    contact['updated'])

        contact['alias'] = self.contacts[uid].get('alias')
        if contact['alias']:
            contact['alias'] = contact['alias'].lower()

        contact['display'] = self.contacts[uid].get('display')
        contact['tags'] = self.contacts[uid].get('tags')
        contact['first'] = self.contacts[uid].get('first')
        contact['last'] = self.contacts[uid].get('last')
        contact['nickname'] = self.contacts[uid].get('nickname')

        contact['birthday'] = self.contacts[uid].get('birthday')
        if contact['birthday']:
            contact['birthday'] = self._datetime_or_none(
                    contact['birthday'])

        contact['anniversary'] = self.contacts[uid].get('anniversary')
        if contact['anniversary']:
            contact['anniversary'] = self._datetime_or_none(
                    contact['anniversary'])

        contact['spouse'] = self.contacts[uid].get('spouse')
        contact['language'] = self.contacts[uid].get('language')
        contact['gender'] = self.contacts[uid].get('gender')
        contact['company'] = self.contacts[uid].get('company')
        contact['title'] = self.contacts[uid].get('title')
        contact['division'] = self.contacts[uid].get('division')
        contact['department'] = self.contacts[uid].get('department')
        contact['manager'] = self.contacts[uid].get('manager')
        contact['assistant'] = self.contacts[uid].get('assistant')
        contact['office'] = self.contacts[uid].get('office')
        contact['calurl'] = self.contacts[uid].get('calurl')
        contact['fburl'] = self.contacts[uid].get('fburl')
        contact['photo'] = self.contacts[uid].get('photo')
        contact['emails'] = self.contacts[uid].get('emails')
        contact['phones'] = self.contacts[uid].get('phones')
        contact['messaging'] = self.contacts[uid].get('messaging')
        contact['addresses'] = self.contacts[uid].get('addresses')
        contact['websites'] = self.contacts[uid].get('websites')
        contact['pgpkeys'] = self.contacts[uid].get('pgpkeys')
        contact['notes'] = self.contacts[uid].get('notes')

        return contact

    @staticmethod
    def _parse_entry(etype, entry):
        """Parses command arguments for emails, phones, messaging
        accounts, websites, and pgpkeys.

        Args:
            etype (str):    the type of entry (email, phone, etc.)
            entry (list):   the list of command arguments.

        Returns:
            data (dict):   the formatted entry data.

        """
        if len(entry) == 3:
            description = entry[0]
            field = entry[1]
            primary = entry[2].lower() == "primary"
        elif len(entry) == 2:
            description = entry[0]
            field = entry[1]
            primary = False
        else:
            description = f"{etype}"
            field = entry[0]
            primary = False
        data = {
            f"{etype}": field,
            "description": description
        }
        if primary:
            data["primary"] = True
        return data

    def _parse_files(self):
        """ Read contact files from `data_dir` and parse contact
        data into `contacts`.

        Returns:
            contacts (dict):    parsed data from each contact file

        """
        this_contact_files = {}
        this_contacts = {}
        aliases = {}

        with os.scandir(self.data_dir) as entries:
            for entry in entries:
                if entry.name.endswith('.yml') and entry.is_file():
                    fullpath = entry.path
                    data = None
                    try:
                        with open(fullpath, "r",
                                  encoding="utf-8") as entry_file:
                            data = yaml.safe_load(entry_file)
                    except (OSError, IOError, yaml.YAMLError):
                        self._error_pass(
                            f"failure reading or parsing {fullpath} "
                            "- SKIPPING")
                    if data:
                        uid = None
                        contact = data.get('contact')
                        if contact:
                            uid = contact.get("uid")
                            alias = contact.get("alias")
                            add_contact = True
                            if uid:
                                # duplicate UID detection
                                dupid = this_contact_files.get(uid)
                                if dupid:
                                    self._error_pass(
                                        "duplicate UID detected:\n"
                                        f"  {uid}\n"
                                        f"  {dupid}\n"
                                        f"  {fullpath}\n"
                                        f"SKIPPING {fullpath}")
                                    add_contact = False
                            if alias:
                                # duplicate alias detection
                                dupalias = aliases.get(alias)
                                if dupalias:
                                    self._error_pass(
                                        "duplicate alias detected:\n"
                                        f"  {alias}\n"
                                        f"  {dupalias}\n"
                                        f"  {fullpath}\n"
                                        f"SKIPPING {fullpath}")
                                    add_contact = False
                            if add_contact:
                                if alias and uid:
                                    this_contacts[uid] = contact
                                    this_contact_files[uid] = fullpath
                                    aliases[alias] = fullpath
                                else:
                                    self._error_pass(
                                        "no uid and/or alias param "
                                        f"in {fullpath} - SKIPPING")
                        else:
                            self._error_pass(
                                f"no data in {fullpath} - SKIPPING")
        self.contacts = this_contacts.copy()
        self.contact_files = this_contact_files.copy()

    def _perform_search(self, term):
        """Parses a search term and returns a list of matching contacts.
        A 'term' can consist of two parts: 'search' and 'exclude'. The
        operator '%' separates the two parts. The 'exclude' part is
        optional.
        The 'search' and 'exclude' terms use the same syntax but differ
        in one noteable way:
          - 'search' is parsed as AND. All parameters must match to
        return a contact record. Note that within a parameter the '+'
        operator is still an OR.
          - 'exclude' is parsed as OR. Any parameters that match will
        exclude a contact record.

        Args:
            term (str):     the search term of contacts to return.

        Returns:
            this_contacts (list):   the contacts matching the search
        criteria.

        """
        # helper lambdas
        def _compare_dates(dtstr, dtobj):
            """Compares a date-like string to a datetime object and
            returns True if the two match.

            Args:
                dtstr (str):    a date-like string.
                dtobj (obj):    a datetime object.

            Returns:
                match (bool):   whether the dtstr and dtobj match.

            """
            match = False
            if (isinstance(dtstr, str) and
                    isinstance(dtobj, datetime)):
                if len(dtstr) == 10:
                    cpstr = datetime.strftime(dtobj, "%Y-%m-%d")
                elif len(dtstr) == 7:
                    cpstr = datetime.strftime(dtobj, "%Y-%m")
                elif len(dtstr) == 5:
                    cpstr = datetime.strftime(dtobj, "%m-%d")
                elif len(dtstr) == 4:
                    cpstr = datetime.strftime(dtobj, "%Y")
                elif len(dtstr) == 2:
                    cpstr = datetime.strftime(dtobj, "%m")
                else:
                    cpstr = ""
                match = dtstr == cpstr
            return match

        # if the exclusion operator is in the provided search term then
        # split the term into two components: search and exclude
        # otherwise, treat it as just a search term alone.
        if "%" in term:
            term = term.split("%")
            searchterm = str(term[0]).lower()
            excludeterm = str(term[1]).lower()
        else:
            searchterm = str(term).lower()
            excludeterm = None

        valid_criteria = [
            "uid=",
            "email=",
            "address=",
            "phone=",
            "alias=",
            "name=",
            "tags=",
            "birthday=",
            "anniversary="
        ]

        # parse the search term into a dict
        if searchterm:
            if searchterm == 'any':
                search = None
            elif not any(x in searchterm for x in valid_criteria):
                # treat this as a simple name search
                search = {}
                search['name'] = searchterm.strip()
            else:
                try:
                    search = dict((k.strip(), v.strip())
                                  for k, v in (item.split('=')
                                  for item in searchterm.split(',')))
                except ValueError:
                    msg = "invalid search expression"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
        else:
            search = None

        # parse the exclude term into a dict
        if excludeterm:
            if not any(x in excludeterm for x in valid_criteria):
                # treat this as a simple name exclusion
                exclude = {}
                exclude['name'] = excludeterm.strip()
            else:
                try:
                    exclude = dict((k.strip(), v.strip())
                                   for k, v in (item.split('=')
                                   for item in excludeterm.split(',')))
                except ValueError:
                    msg = "invalid exclude expression"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
        else:
            exclude = None

        this_contacts = []
        for uid in self.contacts:
            this_contacts.append(uid)
        exclude_list = []

        if exclude:
            x_uid = exclude.get('uid')
            x_alias = exclude.get('alias')
            x_name = exclude.get('name')
            x_email = exclude.get('email')
            x_address = exclude.get('address')
            x_tags = exclude.get('tags')
            if x_tags:
                x_tags = x_tags.split('+')
            x_phone = exclude.get('phone')
            if x_phone:
                x_phone = re.sub(r'\D', '', x_phone)
                if x_phone == "":
                    x_phone = None
            x_birthday = exclude.get('birthday')
            x_anniversary = exclude.get('anniversary')

            for uid in this_contacts:
                contact = self._parse_contact(uid)
                remove = False
                if x_uid:
                    if x_uid == uid:
                        remove = True
                if x_alias:
                    if contact['alias']:
                        if x_alias == contact['alias']:
                            remove = True

                if x_name:
                    if contact['display']:
                        if x_name in contact['display'].lower():
                            remove = True

                # searching for tags allows use of the '+' OR
                # operator, so if we match any tag in the list
                # then exclude the entry
                if x_tags:
                    if contact['tags']:
                        for tag in x_tags:
                            if tag in contact['tags']:
                                remove = True

                if x_birthday:
                    if contact['birthday']:
                        if _compare_dates(x_birthday,
                                          contact['birthday']):
                            remove = True

                if x_anniversary:
                    if contact['anniversary']:
                        if _compare_dates(x_anniversary,
                                          contact['anniversary']):
                            remove = True

                if x_email:
                    if contact['emails']:
                        for entry in contact['emails']:
                            this_email = self._lowered_or_none(
                                    entry.get('email'))
                            if this_email:
                                if x_email in this_email:
                                    remove = True

                if x_phone:
                    if contact['phones']:
                        for entry in contact['phones']:
                            this_phone = entry.get("number")
                            if this_phone:
                                this_phone = re.sub(r'\D', '',
                                                    this_phone)
                                if x_phone in this_phone:
                                    remove = True

                if x_address:
                    if contact['addresses']:
                        for entry in contact['addresses']:
                            address1 = entry.get("address1")
                            address2 = entry.get("address2")
                            city = entry.get("city")
                            state = entry.get("state")
                            zipcode = entry.get("zipcode")
                            country = entry.get("country")
                            this_address = ""
                            addr_elements = [
                                address1,
                                address2,
                                city,
                                state,
                                zipcode,
                                country
                            ]
                            for element in addr_elements:
                                if element:
                                    this_address += f"{element};"
                            if x_address in this_address.lower():
                                remove = True
                if remove:
                    exclude_list.append(uid)

        # remove excluded contacts
        for uid in exclude_list:
            this_contacts.remove(uid)

        not_match = []

        if search:
            s_uid = search.get('uid')
            s_alias = search.get('alias')
            s_name = search.get('name')
            s_email = search.get('email')
            s_address = search.get('address')
            s_tags = search.get('tags')
            if s_tags:
                s_tags = s_tags.split('+')
            s_phone = search.get('phone')
            if s_phone:
                s_phone = re.sub(r'\D', '', x_phone)
                if s_phone == "":
                    s_phone = None
            s_birthday = search.get('birthday')
            s_anniversary = search.get('anniversary')

            for uid in this_contacts:
                contact = self._parse_contact(uid)
                remove = False
                if s_uid:
                    if not s_uid == uid:
                        remove = True
                if s_alias:
                    if contact['alias']:
                        if not s_alias == contact['alias']:
                            remove = True
                    else:
                        remove = True

                if s_name:
                    if contact['display']:
                        if s_name not in contact['display'].lower():
                            remove = True
                    else:
                        remove = True

                # searching for tags allows use of the '+' OR
                # operator, so if we match any tag in the list
                # then keep the entry
                if s_tags:
                    if contact['tags']:
                        keep = False
                        for tag in s_tags:
                            if tag in contact['tags']:
                                keep = True
                        if not keep:
                            remove = True
                    else:
                        remove = True

                if s_birthday:
                    if contact['birthday']:
                        if not _compare_dates(s_birthday,
                                              contact['birthday']):
                            remove = True
                    else:
                        remove = True

                if s_anniversary:
                    if contact['anniversary']:
                        if not _compare_dates(s_anniversary,
                                              contact['anniversary']):
                            remove = True
                    else:
                        remove = True

                if s_email:
                    if contact['emails']:
                        keep = False
                        for entry in contact['emails']:
                            this_email = self._lowered_or_none(
                                    entry.get('email'))
                            if this_email:
                                if s_email in this_email:
                                    keep = True
                        if not keep:
                            remove = True
                    else:
                        remove = True

                if s_phone:
                    if contact['phones']:
                        keep = False
                        for entry in contact['phones']:
                            this_phone = entry.get("number")
                            if this_phone:
                                this_phone = re.sub(r'\D', '', this_phone)
                                if s_phone in this_phone:
                                    keep = True
                        if not keep:
                            remove = True
                    else:
                        remove = True

                if s_address:
                    if contact['addresses']:
                        keep = False
                        for entry in contact['addresses']:
                            address1 = entry.get("address1")
                            address2 = entry.get("address2")
                            city = entry.get("city")
                            state = entry.get("state")
                            zipcode = entry.get("zipcode")
                            country = entry.get("country")
                            this_address = ""
                            addr_elements = [
                                address1,
                                address2,
                                city,
                                state,
                                zipcode,
                                country
                            ]
                            for element in addr_elements:
                                if element:
                                    this_address += f"{element};"
                            if s_address in this_address.lower():
                                keep = True
                        if not keep:
                            remove = True
                    else:
                        remove = True

                if remove:
                    not_match.append(uid)

        # remove the contacts that didn't match search criteria
        for uid in not_match:
            this_contacts.remove(uid)

        return this_contacts

    def _uid_from_alias(self, alias):
        """Get the uid for a valid alias.
        Args:
            alias (str):    The alias of the contact for which to find uid.
        Returns:
            uid (str or None): The uid that matches the submitted alias.
        """
        alias = alias.lower()
        uid = None
        for contact in self.contacts:
            this_alias = self.contacts[contact].get("alias")
            if this_alias:
                if this_alias == alias:
                    uid = contact
        return uid

    def _verify_data_dir(self):
        """Create the contacts data directory if it doesn't exist."""
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
            except IOError:
                self._error_exit(
                    f"{self.data_dir} doesn't exist "
                    "and can't be created"
                )
        elif not os.path.isdir(self.data_dir):
            self._error_exit(f"{self.data_dir} is not a directory")
        elif not os.access(self.data_dir,
                           os.R_OK | os.W_OK | os.X_OK):
            self._error_exit(
                "You don't have read/write/execute permissions to "
                f"{self.data_dir}")

    @staticmethod
    def _write_yaml_file(data, filename):
        """Write YAML data to a file.
        Args:
            data (dict):    the structured data to write.
            filename (str): the location to write the data.
        """
        with open(filename, "w",
                  encoding="utf-8") as out_file:
            yaml.dump(
                data,
                out_file,
                default_flow_style=False,
                sort_keys=False)

    def add_another_email(self):
        """Asks if the user wants to add another email address."""
        another = input("Add another email address? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self.add_new_email()

    def add_confirm_email(
            self,
            description,
            email,
            primary,
            another=True):
        """Confirms the email address parameters entered.

        Args:
            description (str): the email description.
            email (str):       the email address.
            primary (bool):    is primary email address.
            another (bool):    offer to add another when complete.

        """
        if not email:
            self._error_pass("email address cannot be blank")
            self.add_new_email(another)
        else:
            print(
                "\n"
                "  New email address:\n"
                f"    description: {description}\n"
                f"    email: {email}\n"
                f"    primary: {primary}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                data = [description, email]
                if primary:
                    data.append("primary")
                if not self.add_emails:
                    self.add_emails = []
                self.add_emails.append(data)
                if another:
                    self.add_another_email()
            else:
                self.add_new_email(another)

    def add_from_mutt(self, filename):
        """Add a new contact from mutt/neomutt by parsing the From: address
        from the message header.

        Args:
            filename (str): filename of the message piped from mutt.

        """
        filename = os.path.expandvars(os.path.expanduser(filename))
        os.system("cls" if os.name == "nt" else "clear")
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as email_file:
                    email_txt = email_file.read().strip()
            except IOError:
                input(
                    "ERROR: failed to read email file."
                    "Press Enter to continue...")
            else:
                message = HeaderParser().parsestr(email_txt)
                headers = dict(message)
                from_line = headers.get("From")
                if from_line:
                    from_name = None
                    from_email = None
                    if '" <' in from_line:
                        from_line = from_line.split('" <')
                        if len(from_line) > 1:
                            from_name = from_line[0].replace('"', '')
                            from_email = from_line[1].replace('>', '')
                        else:
                            from_email = (
                                from_line[0]
                                .replace('"', '')
                                .replace('<', '')
                                .replace('>', ''))
                    else:
                        from_line = from_line.split()
                        if len(from_line) > 1:
                            from_name = from_line[0].replace('"', '')
                            from_email = (
                                from_line[1]
                                .replace('<', '')
                                .replace('>', ''))
                        else:
                            from_email = (
                                from_line[0]
                                .replace('"', '')
                                .replace('<', '')
                                .replace('>', ''))
                    if not from_email:
                        input(
                            "ERROR: No From: email address found. "
                            "Press Enter to continue...")
                        sys.exit(1)
                    else:
                        email_exists = False
                        exist_alias = None
                        for uid in self.contacts:
                            alias = self.contacts[uid].get('alias')
                            emails = self.contacts[uid].get('emails')
                            if emails:
                                for entry in emails:
                                    address = entry.get('email')
                                    if address == from_email:
                                        email_exists = True
                                        exist_alias = alias
                        if email_exists:
                            input(
                                f"ERROR: Address '{from_email}' already "
                                f"exists in contact {exist_alias}. "
                                "Press Enter to continue...")
                            sys.exit(1)
                        else:
                            print("\nFound sender:")
                            print(f"  name:  {from_name}")
                            print(f"  email: {from_email}\n")
                            self.new(
                                display=from_name,
                                emails=[['mutt', from_email]])
                            time.sleep(3)
                            sys.exit(0)
                else:
                    input("ERROR: No From: address in email file. "
                          "Press Enter to continue...")
                    sys.exit(1)
        else:
            input(
                "ERROR: Failed to read email file."
                "Press Enter to continue...")
            sys.exit(1)

    def add_new_email(self, another=True):
        """Prompts the user through adding a new email address
        to a contact.

        Args:
            another (bool):    offer to add another when complete.

        """
        description = input("Address description [email]: ") or "email"
        new_email = input("Email address []: ") or None
        isprimary = input("Primary address? [N/y]: ").lower()
        primary = isprimary in ['y', 'yes']
        self.add_confirm_email(description, new_email, primary, another)

    def add_another_phone(self):
        """Asks if the user wants to add another phone number."""
        another = input("Add another phone number? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self.add_new_phone()

    def add_confirm_phone(
            self,
            description,
            number,
            primary,
            another=True):
        """Confirms the phone number parameters entered.

        Args:
            description (str): the phone description.
            number (str):       the phone number.
            primary (bool):    is primary phone number.
            another (bool):    offer to add another when complete.

        """
        if not number:
            self._error_pass("phone number cannot be blank")
            self.add_new_phone(another)
        else:
            print(
                "\n"
                "  New phone number:\n"
                f"    description: {description}\n"
                f"    number: {number}\n"
                f"    primary: {primary}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                data = [description, number]
                if primary:
                    data.append("primary")
                if not self.add_phones:
                    self.add_phones = []
                self.add_phones.append(data)
                if another:
                    self.add_another_phone()
            else:
                self.add_new_phone(another)

    def add_new_phone(self, another=True):
        """Prompts the user through adding a new phone number
        to a contact.

        Args:
            another (bool):    offer to add another when complete.

        """
        description = (
                input("Number description [number]: ")
                or "number")
        number = input("Phone number []: ") or None
        isprimary = input("Primary number? [N/y]: ").lower()
        primary = isprimary in ['y', 'yes']
        self.add_confirm_phone(description, number, primary, another)

    def add_another_messaging(self):
        """Asks if the user wants to add another messaging account."""
        another = input(
                "Add another messaging account? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self.add_new_messaging()

    def add_confirm_messaging(
            self,
            description,
            account,
            primary,
            another=True):
        """Confirms the messaging account parameters entered.

        Args:
            description (str): the account description.
            account (str):       the messaging account address.
            primary (bool):    is primary messaging account.
            another (bool):    offer to add another when complete.

        """
        if not account:
            self._error_pass("account address cannot be blank")
            self.add_new_messaging(another)
        else:
            print(
                "\n"
                "  New messaging account:\n"
                f"    description: {description}\n"
                f"    account: {account}\n"
                f"    primary: {primary}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                data = [description, account]
                if primary:
                    data.append("primary")
                if not self.add_messaging:
                    self.add_messaging = []
                self.add_messaging.append(data)
                if another:
                    self.add_another_messaging()
            else:
                self.add_new_messaging(another)

    def add_new_messaging(self, another=True):
        """Prompts the user through adding a new messaging
        account to a contact.

        Args:
            another (bool):    offer to add another when complete.

        """
        description = (
                input("Account description [account]: ")
                or "account")
        account = input("Messaging account []: ") or None
        isprimary = input("Primary account? [N/y]: ").lower()
        primary = isprimary in ['y', 'yes']
        self.add_confirm_messaging(description, account, primary, another)

    def add_another_address(self):
        """Asks if the user wants to add another address."""
        another = input(
                "Add another address? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self.add_new_address()

    def add_confirm_address(
            self,
            description,
            address1,
            address2,
            city,
            state,
            zipcode,
            country,
            primary,
            another=True):
        """Confirms the address parameters entered.

        Args:
            description (str):  the address description.
            address1 (str):     address line 1.
            address2 (str):     address line 2.
            city (str):         the address city.
            state (str):        the address state.
            zipcode (str):      the address zip/postal code.
            country (str):      the address country.
            primary (bool):     is primary address.
            another (bool):    offer to add another when complete.

        """
        testaddr = (
                f"{address1}{address2}{city}{state}"
                f"{zipcode}{country}"
        )

        if not len(testaddr) > 0:
            self._error_pass("address cannot be blank")
            self.add_new_address(another)
        else:
            faddress = ""
            if address1 != '':
                faddress += f"      {address1}\n"
            if address2 != '':
                faddress += f"      {address2}\n"
            if city != '' and state != '' and zipcode != '':
                faddress += f"      {city}, {state} {zipcode}\n"
            elif city != '' and state != '':
                faddress += f"      {city}, {state}\n"
            elif city != '' or state != '' or zipcode != '':
                faddress += (f"{city} {state} {zipcode}\n"
                             .strip()
                             .replace("  ", " ")
                             )
            if country != '':
                faddress += f"      {country}\n"

            print(
                "\n"
                "  New address:\n"
                f"    description: {description}\n"
                "    address:\n"
                f"{faddress}"
                f"    primary: {primary}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                address = (
                        f"{address1};{address2};{city};{state};"
                        f"{zipcode};{country}"
                )
                data = [description, address]
                if primary:
                    data.append("primary")
                if not self.add_addresses:
                    self.add_addresses = []
                self.add_addresses.append(data)
                if another:
                    self.add_another_address()
            else:
                self.add_new_address(another)

    def add_new_address(self, another=True):
        """Prompts the user through adding a new address
        to a contact.

        Args:
            another (bool):    offer to add another when complete.

        """
        description = (
                input("Address description [address]: ")
                or "address")
        address1 = input("Street line 1 []: ") or None
        address2 = input("Street line 2 (optional) []: ") or None
        city = input("City []: ") or None
        state = input("State []: ") or None
        zipcode = input("Postal code []: ") or None
        country = input("Country []: ") or None
        isprimary = input("Primary address? [N/y]: ").lower()
        primary = isprimary in ['y', 'yes']
        self.add_confirm_address(
            description,
            address1,
            address2,
            city,
            state,
            zipcode,
            country,
            primary,
            another
        )

    def add_another_website(self):
        """Asks if the user wants to add another website."""
        another = input(
                "Add another website? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self.add_new_website()

    def add_confirm_website(
            self,
            description,
            url,
            primary,
            another=True):
        """Confirms the website parameters entered.

        Args:
            description (str): the website description.
            url (str):       the website URL.
            primary (bool):    is primary website.
            another (bool):    offer to add another when complete.

        """
        if not url:
            self._error_pass("website URL cannot be blank")
            self.add_new_website(another)
        else:
            print(
                "\n"
                "  New website:\n"
                f"    description: {description}\n"
                f"    url: {url}\n"
                f"    primary: {primary}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                data = [description, url]
                if primary:
                    data.append("primary")
                if not self.add_websites:
                    self.add_websites = []
                self.add_websites.append(data)
                if another:
                    self.add_another_website()
            else:
                self.add_new_website(another)

    def add_new_website(self, another=True):
        """Prompts the user through adding a new website URL
        to a contact.

        Args:
            another (bool):    offer to add another when complete.

        """
        description = (
                input("Website description [url]: ")
                or "website")
        url = input("Website URL []: ") or None
        isprimary = input("Primary website? [N/y]: ").lower()
        primary = isprimary in ['y', 'yes']
        self.add_confirm_website(description, url, primary, another)

    def add_another_pgpkey(self):
        """Asks if the user wants to add another PGP key URL."""
        another = input(
                "Add another PGP key? [N/y]: ").lower()
        if another in ['y', 'yes']:
            self.add_new_pgpkey()

    def add_confirm_pgpkey(
            self,
            description,
            url,
            primary,
            another=True):
        """Confirms the PGP key parameters entered.

        Args:
            description (str): the PGP key description.
            url (str):       the PGP key URL.
            primary (bool):    is primary PGP key.
            another (bool):    offer to add another when complete.

        """
        if not url:
            self._error_pass("key URL cannot be blank")
            self.add_new_pgpkey(another)
        else:
            print(
                "\n"
                "  New PGP key:\n"
                f"    description: {description}\n"
                f"    url: {url}\n"
                f"    primary: {primary}\n"
            )
            confirm = input("Is this correct? [N/y]: ").lower()
            if confirm in ['y', 'yes']:
                data = [description, url]
                if primary:
                    data.append("primary")
                if not self.add_pgpkeys:
                    self.add_pgpkeys = []
                self.add_pgpkeys.append(data)
                if another:
                    self.add_another_pgpkey()
            else:
                self.add_new_pgpkey(another)

    def add_new_pgpkey(self, another=True):
        """Prompts the user through adding a new PGP key
        to a contact.

        Args:
            another (bool):    offer to add another when complete.

        """
        description = (
                input("Key description [url]: ")
                or "")
        url = input("PGP key URL []: ") or None
        isprimary = input("Primary PGP key? [N/y]: ").lower()
        primary = isprimary in ['y', 'yes']
        self.add_confirm_pgpkey(description, url, primary, another)

    def delete(self, alias, force=False):
        """Delete a contact identified by alias.

        Args:
            term (str):    The alias of the contact to be deleted.

        """
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            filename = self.contact_files.get(uid)
            if filename:
                if force:
                    confirm = "yes"
                else:
                    confirm = input(f"Delete '{alias}'? [N/y]: ").lower()
                if confirm in ['yes', 'y']:
                    try:
                        os.remove(filename)
                    except OSError:
                        self._handle_error(f"failure deleting {filename}")
                    else:
                        print(f"Deleted contact: {alias}")
                else:
                    print("Cancelled")
            else:
                self._handle_error(f"failed to find file for {alias}")

    def edit(self, alias):
        """Edit a contact file identified by alias (using $EDITOR).

        Args:
            term (str):    The alias of the contact to be edited.

        """
        if self.editor:
            alias = alias.lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                self._alias_not_found(alias)
            else:
                filename = self.contact_files.get(uid)
                if filename:
                    try:
                        subprocess.run([self.editor, filename], check=True)
                    except subprocess.SubprocessError:
                        self._handle_error(
                            f"failure editing file {filename}")
                else:
                    self._handle_error(f"failed to find file for {alias}")
        else:
            self._handle_error("$EDITOR is required and not set")

    def edit_config(self):
        """Edit the config file (using $EDITOR) and then reload config."""
        if self.editor:
            try:
                subprocess.run(
                    [self.editor, self.config_file], check=True)
            except subprocess.SubprocessError:
                self._handle_error("failure editing config file")
            else:
                if self.interactive:
                    self._parse_config()
                    self.refresh()
        else:
            self._handle_error("$EDITOR is required and not set")

    def export(self, term, filename=None):
        """Search contacts by email address, phone number, alias,
        name, tag, address, or any and output matches in vCard 4.0
        format.

        A 'term' can consist of two parts: 'search' and 'exclude'. The
        operator '%' separates the two parts. The 'exclude' part is
        optional.
        The 'search' and 'exclude' terms use the same syntax but differ
        in one noteable way:
          - 'search' is parsed as AND. All parameters must match to
        return a contact record. Note that within a parameter the '+'
        operator is still an OR.
          - 'exclude' is parsed as OR. Any parameters that match will
        exclude a contact record.

        Args:
            term (str):     the search term of contacts to export.
            filename(str): Optional. Filename to write vCard output.
        This param is only useful in shell mode where redirection is
        not possible.

        """
        def _export_timestamp(timeobj):
            """Print a datetime string in iCalendar-compatible format.

            Args:
                timeobj (obj):  a datetime object.
            minutes, and seconds

            Returns:
                timestr (str):  a datetime string.

            """
            timestr = (timeobj.astimezone(tz=timezone.utc)
                       .strftime("%Y%m%dT%H%M%SZ"))
            return timestr

        def _export_wrap(text, length=75):
            """Wraps text that exceeds a given line length, with an
            indentation of one space on the next line.

            Args:
                text (str): the text to be wrapped.
                length (int): the maximum line length (default: 75).

            Returns:
                wrapped (str): the wrapped text.

            """
            wrapper = TextWrapper(
                width=length,
                subsequent_indent=' ',
                drop_whitespace=False,
                break_long_words=True)
            wrapped = '\r\n'.join(wrapper.wrap(text))
            return wrapped

        results = self._perform_search(term)

        output = ""
        if len(results) > 0:
            for uid in results:
                contact = self._parse_contact(uid)

                vcard = (
                    "BEGIN:VCARD\r\n"
                    "VERSION:4.0\r\n"
                    f"PRODID:-//sdoconnell.net/{APP_NAME} {APP_VERS}//EN\r\n"
                    f"UID:{uid}\r\n"
                )
                if contact['first'] or contact['last']:
                    vcard += "KIND:individual\r\n"
                else:
                    vcard += "KIND:org\r\n"

                # personal fields
                if contact['display']:
                    fntxt = _export_wrap(f"FN:{contact['display']}")
                    vcard += f"{fntxt}\r\n"

                if contact['first'] or contact['last']:
                    if not contact['first']:
                        contact['first'] = ""
                    if not contact['last']:
                        contact['last'] = ""
                    ntxt = _export_wrap(
                            f"N:{contact['last']};{contact['first']};;;")
                    vcard += f"{ntxt}\r\n"

                if contact['nickname']:
                    nicknametxt = _export_wrap(
                            f"NICKNAME:{contact['nickname']}")
                    vcard += f"{nicknametxt}\r\n"

                if contact['language']:
                    langtxt = _export_wrap(f"LANG:{contact['language']}")
                    vcard += f"{langtxt}\r\n"

                if contact['gender']:
                    gendertxt = _export_wrap(f"GENDER:{contact['gender']}")
                    vcard += f"{gendertxt}\r\n"

                if contact['birthday']:
                    birthday = _export_timestamp(
                            contact['birthday'])
                    vcard += f"BDAY:{birthday}\r\n"

                if contact['anniversary']:
                    anniversary = _export_timestamp(
                            contact['anniversary'])
                    vcard += f"ANNIVERSARY:{anniversary}\r\n"

                if contact['spouse']:
                    spousetxt = _export_wrap(
                        f"RELATED;TYPE=spouse;"
                        f"VALUE=text:{contact['spouse']}")
                    vcard += f"{spousetxt}\r\n"

                # business fields
                org = []
                if contact['company']:
                    org.append(contact['company'])
                if contact['division']:
                    org.append(contact['division'])
                if contact['department']:
                    org.append(contact['department'])
                if len(org) > 0:
                    orgtxt = f"ORG:{';'.join(org)}"
                    vcard += f"{orgtxt}\r\n"

                if contact['title']:
                    titletxt = _export_wrap(f"TITLE:{contact['title']}")
                    vcard += f"{titletxt}\r\n"

                if contact['manager']:
                    managertxt = _export_wrap(
                        f"RELATED;TYPE=co-worker;"
                        f"VALUE=text:{contact['manager']} (manager)")
                    vcard += f"{managertxt}\r\n"

                if contact['assistant']:
                    assistanttxt = _export_wrap(
                        f"RELATED;TYPE=co-worker;"
                        f"VALUE=text:{contact['assistant']} (assistant)")
                    vcard += f"{assistanttxt}\r\n"

                if contact['emails']:
                    if contact['emails'][0].get("email"):
                        for entry in contact['emails']:
                            primary = entry.get("primary")
                            this_email = entry.get("email")
                            description = entry.get("description")
                            params = []
                            if description:
                                description = (
                                    description
                                    .upper()
                                    .replace("-", ",")
                                )
                                params.append(f"TYPE={description}")
                            if primary:
                                params.append("PREF=1")
                            if this_email:
                                if params:
                                    emailtxt = _export_wrap(
                                        f"EMAIL;{';'.join(params)}:"
                                        f"{this_email}")
                                else:
                                    emailtxt = _export_wrap(
                                            f"EMAIL:{this_email}")
                                vcard += f"{emailtxt}\r\n"

                if contact['phones']:
                    if contact['phones'][0].get("number"):
                        for entry in contact['phones']:
                            primary = entry.get("primary")
                            number = entry.get("number")
                            description = entry.get("description")
                            params = []
                            if description:
                                description = (
                                    description
                                    .upper()
                                    .replace("-", ",")
                                )
                                params.append(f"TYPE={description}")
                            if primary:
                                params.append("PREF=1")
                            if number:
                                if params:
                                    teltxt = _export_wrap(
                                        f"TEL;{';'.join(params)}:{number}")
                                else:
                                    teltxt = _export_wrap(f"TEL:{number}")
                                vcard += f"{teltxt}\r\n"

                if contact['messaging']:
                    if contact['messaging'][0].get("account"):
                        for entry in contact['messaging']:
                            primary = entry.get("primary")
                            account = entry.get("account")
                            description = entry.get("description")
                            if primary:
                                vpref = ";PREF=1"
                            if description and account:
                                impptxt = _export_wrap(
                                    f"IMPP{vpref}:{description}:{account}")
                                vcard += f"{impptxt}\r\n"

                if contact['addresses']:
                    if (contact['addresses'][0].get("address1") or
                            contact['addresses'][0].get("address2") or
                            contact['addresses'][0].get("city") or
                            contact['addresses'][0].get("state") or
                            contact['addresses'][0].get("zipcode") or
                            contact['addresses'][0].get("country")):

                        for entry in contact['addresses']:
                            primary = entry.get("primary")
                            address = ""
                            address1 = entry.get("address1")
                            address2 = entry.get("address2")
                            city = entry.get("city")
                            state = entry.get("state")
                            zipcode = entry.get("zipcode")
                            country = entry.get("country")
                            description = entry.get('description')
                            if description:
                                description = (
                                    description
                                    .upper()
                                    .replace("-", ","))
                            if address1 and address2:
                                address = (
                                    f"{address1}"
                                    r"\,"
                                    f"{address2}"
                                )
                            elif address1:
                                address = address1
                            else:
                                address = ""
                            if not city:
                                city = ""
                            if not state:
                                state = ""
                            if not zipcode:
                                zipcode = ""
                            if not country:
                                country = ""
                            combined = (
                                f";;{address};{city};{state};"
                                f"{zipcode};{country}"
                            )
                            params = []
                            if description:
                                params.append(f"TYPE={description}")
                            if primary:
                                params.append("PREF=1")
                            if params:
                                adrtxt = _export_wrap(
                                    f"ADR;{';'.join(params)}:"
                                    f"{combined}")
                            else:
                                adrtxt = _export_wrap(
                                    f"ADR:{combined}")
                            vcard += f"{adrtxt}\r\n"

                if contact['websites']:
                    if contact['websites'][0].get("url"):
                        for entry in contact['websites']:
                            primary = entry.get("primary")
                            url = entry.get("url")
                            description = entry.get('description')
                            if description:
                                description = (
                                    description
                                    .upper()
                                    .replace("-", ","))
                            if url:
                                params = []
                                if description:
                                    params.append(
                                        f"TYPE={description}")
                                if primary:
                                    params.append("PREF=1")
                                if params:
                                    urltxt = _export_wrap(
                                            f"URL;{';'.join(params)}:{url}")
                                else:
                                    urltxt = _export_wrap(f"URL:{url}")
                                vcard += f"{urltxt}\r\n"

                if contact['pgpkeys']:
                    if contact['pgpkeys'][0].get("url"):
                        for entry in contact['pgpkeys']:
                            primary = entry.get("primary")
                            url = entry.get("url")
                            description = entry.get('description')
                            if description:
                                description = (
                                    description
                                    .upper()
                                    .replace("-", ","))
                            if url:
                                params = []
                                if description:
                                    params.append(
                                        f"TYPE={description}")
                                if primary:
                                    params.append("PREF=1")
                                if params:
                                    keytxt = _export_wrap(
                                        f"KEY;{';'.join(params)}:{url}")
                                else:
                                    keytxt = _export_wrap(f"KEY:{url}")
                                vcard += f"{keytxt}\r\n"

                if contact['photo']:
                    if contact['photo'].startswith("http"):
                        phototxt = _export_wrap(f"PHOTO:{contact['photo']}")
                        vcard += f"{phototxt}\r\n"
                    elif contact['photo'].startswith("file"):
                        if contact['photo'].endswith(".jpg"):
                            mime_type = "image/jpeg"
                        elif contact['photo'].endswith(".png"):
                            mime_type = "image/png"
                        elif contact['photo'].endswith(".gif"):
                            mime_type = "image/gif"
                        else:
                            mime_type = None

                        if mime_type:
                            photofile = contact['photo'].replace("file://", "")
                            if os.access(photofile, os.R_OK):
                                image = None
                                try:
                                    with open(photofile, "rb") as pfile:
                                        image = pfile.read()
                                except OSError:
                                    pass
                                else:
                                    if image:
                                        image64 = (base64.b64encode(image)
                                                   .decode())
                                        phototxt = _export_wrap(
                                            f"PHOTO:data:{mime_type};base64,"
                                            f"{image64}",
                                            70)
                                        vcard += f"{phototxt}\r\n"

                if contact['calurl']:
                    if contact['calurl'].endswith(".ics"):
                        caluritxt = _export_wrap(
                                "CALURI;MEDIATYPE=text/calendar:"
                                f"{contact['calurl']}")
                    else:
                        caluritxt = _export_wrap(f"CALURI:{contact['calurl']}")
                    vcard += f"{caluritxt}\r\n"

                if contact['fburl']:
                    if contact['fburl'].endswith(".ifb"):
                        fburltxt = _export_wrap(
                                "FBURL;MEDIATYPE=text/calendar:"
                                f"{contact['fburl']}")
                    else:
                        fburltxt = _export_wrap(f"FBURL:{contact['fburl']}")
                    vcard += f"{fburltxt}\r\n"

                if contact['notes']:
                    notes = contact['notes'].replace("\n", "\\n")
                    notetxt = _export_wrap(f"NOTE:{notes}")
                    vcard += f"{notetxt}\r\n"

                if contact['tags']:
                    tags = ','.join(contact['tags']).upper()
                    categoriestxt = _export_wrap(f"CATEGORIES:{tags}")
                    vcard += f"{categoriestxt}\r\n"

                updated = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                vcard += f"REV;VALUE=DATE-AND-OR-TIME:{updated}\r\n"
                vcard += "END:VCARD\r\n"
                output += vcard

        else:
            print("No records found.")
        if filename:
            filename = os.path.expandvars(os.path.expanduser(filename))
            try:
                with open(filename, "w",
                          encoding="utf-8") as vcard_file:
                    vcard_file.write(output)
            except (OSError, IOError):
                print("ERROR: unable to write vCard file.")
            else:
                print(f"vCard written to {filename}.")
        else:
            print(output)

    def info(self, alias, pager=False):
        """Display full information for a contact identified by alias.

        Args:
            alias (str):    The alias of the record to be diplayed.
            pager (bool):   Pipe output through console.pager.

        """
        def _make_description(primary, description, index):
            """Format the description field for entries.

            Args:
                primary (bool):     this is a primary entry.
                description (str):  the entry description.
                index (int):        the entry index number.

            """
            if primary and self.color_bold:
                description = (
                    f"[bold {self.color_infoprimary}]"
                    f"[{index + 1}] {description}[/bold "
                    f"{self.color_infoprimary}]"
                )
            elif primary:
                description = (
                    f"[{self.color_infoprimary}]"
                    f"[{index + 1}] {description}"
                    f"[/{self.color_infoprimary}]"
                )
            else:
                description = (
                    f"[{index + 1}] {description}"
                )
            return description

        console = Console()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            contact = self._parse_contact(uid)

            # header table
            header_table = Table(
                title=None,
                box=box.SIMPLE,
                show_header=False,
                show_lines=False,
                pad_edge=False,
                collapse_padding=False,
                padding=(0, 0, 0, 0))
            # columns
            header_table.add_column("field")
            # rows
            header_table.add_row(
                contact['display'],
                style=self.style_infoheader)
            if contact['title'] or contact['company']:
                if contact['title'] and contact['company']:
                    header_table.add_row(
                        f"{contact['title']}, {contact['company']}",
                        style=self.style_infosubheader)
                elif contact['title']:
                    header_table.add_row(
                        contact['title'],
                        style=self.style_infosubheader)
                elif contact['company']:
                    header_table.add_row(
                        contact['company'],
                        style=self.style_infosubheader)

            # contact record table
            record_table = Table(
                title="Contact",
                title_justify="left",
                title_style=self.style_infosection,
                box=box.SIMPLE,
                show_header=False,
                show_lines=False,
                padding=(0, 0, 0, 0))
            # columns
            record_table.add_column(
                "field",
                width=14,
                style=self.style_infolabel)
            record_table.add_column(
                "data",
                style=self.style_infofield)
            # rows
            record_table.add_row("alias:", alias.lower())
            record_table.add_row("uid:", uid)
            if contact['created']:
                created = self._format_timestamp(contact['created'])
                record_table.add_row("created:", created)
            if contact['updated']:
                updated = self._format_timestamp(contact['updated'])
                record_table.add_row("updated:", updated)
            if contact['tags']:
                record_table.add_row("tags:", ','.join(contact['tags']))

            if (contact['first'] or
                    contact['last'] or
                    contact['nickname'] or
                    contact['birthday'] or
                    contact['anniversary'] or
                    contact['spouse'] or
                    contact['language'] or
                    contact['gender']):
                # personal info table
                personal_table = Table(
                    title="Personal info",
                    title_justify="left",
                    title_style=self.style_infosection,
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    padding=(0, 0, 0, 0))
                # columns
                personal_table.add_column(
                    "field",
                    width=14,
                    style=self.style_infolabel)
                personal_table.add_column(
                    "data",
                    style=self.style_infofield)
                # rows
                if contact['first']:
                    personal_table.add_row("first name:", contact['first'])
                if contact['last']:
                    personal_table.add_row("last name:", contact['last'])
                if contact['nickname']:
                    personal_table.add_row("nickname:", contact['nickname'])
                if contact['birthday']:
                    birthday = self._format_timestamp(
                            contact['birthday'], True)
                    personal_table.add_row("birthday:", birthday)
                if contact['anniversary']:
                    anniversary = self._format_timestamp(
                            contact['anniversary'], True)
                    personal_table.add_row(
                        "anniversary:", anniversary)
                if contact['spouse']:
                    personal_table.add_row("spouse:", contact['spouse'])
                if contact['language']:
                    personal_table.add_row("language:", contact['language'])
                if contact['gender']:
                    personal_table.add_row("gender:", contact['gender'])

            if (contact['company'] or
                    contact['title'] or
                    contact['division'] or
                    contact['department'] or
                    contact['manager'] or
                    contact['assistant'] or
                    contact['office']):
                # business info table
                business_table = Table(
                    title="Business info",
                    title_justify="left",
                    title_style=self.style_infosection,
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    padding=(0, 0, 0, 0))
                # columns
                business_table.add_column(
                    "field",
                    width=14,
                    style=self.style_infolabel)
                business_table.add_column(
                    "data",
                    style=self.style_infofield)
                # rows
                if contact['company']:
                    business_table.add_row("company:", contact['company'])
                if contact['title']:
                    business_table.add_row("title:", contact['title'])
                if contact['division']:
                    business_table.add_row("division:", contact['division'])
                if contact['department']:
                    business_table.add_row("department:",
                                           contact['department'])
                if contact['manager']:
                    business_table.add_row("manager:", contact['manager'])
                if contact['assistant']:
                    business_table.add_row("assistant:", contact['assistant'])
                if contact['office']:
                    business_table.add_row("office:", contact['office'])

            if contact['emails']:
                if contact['emails'][0].get("email"):
                    # email table
                    email_table = Table(
                        title="Email",
                        title_justify="left",
                        title_style=self.style_infosection,
                        box=box.SIMPLE,
                        show_header=False,
                        show_lines=False,
                        padding=(0, 0, 0, 0))
                    # columns
                    email_table.add_column(
                        "description",
                        width=14,
                        style=self.style_infolabel)
                    email_table.add_column(
                        "address",
                        style=self.style_infofield)
                    for index, entry in enumerate(contact['emails']):
                        primary = entry.get("primary")
                        this_email = entry.get("email")
                        description = f'{entry.get("description", "email")}:'
                        if this_email:
                            description = _make_description(
                                primary,
                                description,
                                index)
                            email_table.add_row(description, this_email)

            if contact['phones']:
                if contact['phones'][0].get("number"):
                    # phone table
                    phone_table = Table(
                        title="Phone",
                        title_justify="left",
                        title_style=self.style_infosection,
                        box=box.SIMPLE,
                        show_header=False,
                        show_lines=False,
                        padding=(0, 0, 0, 0))
                    # columns
                    phone_table.add_column(
                        "description",
                        width=14,
                        style=self.style_infolabel)
                    phone_table.add_column(
                        "number",
                        style=self.style_infofield)
                    for index, entry in enumerate(contact['phones']):
                        primary = entry.get("primary")
                        number = entry.get("number")
                        description = f'{entry.get("description", "number")}:'
                        if number:
                            description = _make_description(
                                primary,
                                description,
                                index)
                            phone_table.add_row(description, number)

            if contact['messaging']:
                if contact['messaging'][0].get("account"):
                    # messaging table
                    messaging_table = Table(
                        title="Messaging",
                        title_justify="left",
                        title_style=self.style_infosection,
                        box=box.SIMPLE,
                        show_header=False,
                        show_lines=False,
                        padding=(0, 0, 0, 0))
                    # columns
                    messaging_table.add_column(
                        "description",
                        width=14,
                        style=self.style_infolabel)
                    messaging_table.add_column(
                        "account",
                        style=self.style_infofield)
                    for index, entry in enumerate(contact['messaging']):
                        primary = entry.get("primary")
                        account = entry.get("account")
                        description = (
                            f'{entry.get("description", "protocol")}:'
                        )
                        if account:
                            description = _make_description(
                                primary,
                                description,
                                index)
                            messaging_table.add_row(
                                description,
                                account)

            if contact['addresses']:
                if (contact['addresses'][0].get("address1") or
                        contact['addresses'][0].get("address2") or
                        contact['addresses'][0].get("city") or
                        contact['addresses'][0].get("state") or
                        contact['addresses'][0].get("zipcode") or
                        contact['addresses'][0].get("country")):
                    # addresses table
                    addresses_table = Table(
                        title="Addresses",
                        title_justify="left",
                        title_style=self.style_infosection,
                        box=box.SIMPLE,
                        show_header=False,
                        show_lines=False,
                        padding=(0, 0, 0, 0))
                    # columns
                    addresses_table.add_column(
                        "description",
                        width=14,
                        style=self.style_infolabel)
                    addresses_table.add_column(
                        "address",
                        style=self.style_infofield)
                    for index, entry in enumerate(contact['addresses']):
                        primary = entry.get("primary")
                        address = ""
                        address1 = entry.get("address1")
                        address2 = entry.get("address2")
                        city = entry.get("city")
                        state = entry.get("state")
                        zipcode = entry.get("zipcode")
                        country = entry.get("country")
                        description = (
                            f"{entry.get('description', 'address')}:"
                        )
                        if address1:
                            address += f"{address1}\n"
                        if address2:
                            address += f"{address2}\n"
                        if not city:
                            city = ""
                        if not state:
                            state = ""
                        if not zipcode:
                            zipcode = ""

                        if city != "" and state != "" and zipcode != "":
                            address += f"{city}, {state} {zipcode}\n"
                        elif city != "" and state != "":
                            address += f"{city}, {state}\n"
                        else:
                            address += (f"{city} {state} {zipcode}\n"
                                        .strip()
                                        .replace("  ", " ")
                                        )
                        if country:
                            if entry == list(contact["addresses"])[-1]:
                                address += f"{country}"
                            else:
                                address += f"{country}\n"
                        if address != "":
                            description = _make_description(
                                primary,
                                description,
                                index)
                            addresses_table.add_row(
                                description,
                                address)

            if contact['websites']:
                if contact['websites'][0].get("url"):
                    # websites table
                    websites_table = Table(
                        title="Websites",
                        title_justify="left",
                        title_style=self.style_infosection,
                        box=box.SIMPLE,
                        show_header=False,
                        show_lines=False,
                        padding=(0, 0, 0, 0))
                    # columns
                    websites_table.add_column(
                        "description",
                        width=14,
                        style=self.style_infolabel)
                    websites_table.add_column(
                        "website",
                        style=self.style_infofield)
                    for index, entry in enumerate(contact['websites']):
                        primary = entry.get("primary")
                        link = entry.get("url")
                        url = f"[link={link}]{link}[/link]"
                        description = (
                            f"{entry.get('description', 'website')}:"
                        )
                        if url:
                            description = _make_description(
                                primary,
                                description,
                                index)
                            websites_table.add_row(description, url)

            if contact['pgpkeys']:
                if contact['pgpkeys'][0].get("url"):
                    # pgpkeys table
                    pgpkeys_table = Table(
                        title="PGP keys",
                        title_justify="left",
                        title_style=self.style_infosection,
                        box=box.SIMPLE,
                        show_header=False,
                        show_lines=False,
                        padding=(0, 0, 0, 0))
                    # columns
                    pgpkeys_table.add_column(
                        "description",
                        width=14,
                        style=self.style_infolabel)
                    pgpkeys_table.add_column(
                        "pgpkey",
                        style=self.style_infofield)
                    for index, entry in enumerate(contact['pgpkeys']):
                        primary = entry.get("primary")
                        url = entry.get("url")
                        description = (
                            f"{entry.get('description', 'url')}:"
                        )
                        if url:
                            description = _make_description(
                                primary,
                                description,
                                index)
                            pgpkeys_table.add_row(description, url)

            if contact['photo']:
                # misc table
                misc_table = Table(
                    title="Miscellaneous",
                    title_justify="left",
                    title_style=self.style_infosection,
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    padding=(0, 0, 0, 0))
                # columns
                misc_table.add_column(
                    "field",
                    width=14,
                    style=self.style_infolabel)
                misc_table.add_column(
                    "url",
                    style=self.style_infofield)
                misc_table.add_row("photo", contact['photo'])

            if contact['calurl'] or contact['fburl']:
                # calendar table
                calendar_table = Table(
                    title="Calendar",
                    title_justify="left",
                    title_style=self.style_infosection,
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    padding=(0, 0, 0, 0))
                # columns
                calendar_table.add_column(
                    "field",
                    width=14,
                    style=self.style_infolabel)
                calendar_table.add_column(
                    "data",
                    style=self.style_infofield)
                if contact['calurl']:
                    calendar_table.add_row('url:', contact['calurl'])
                if contact['fburl']:
                    calendar_table.add_row('freebusy:', contact['fburl'])

            if contact['notes']:
                # notes table
                notes_table = Table(
                    title="Notes",
                    title_justify="left",
                    title_style=self.style_infosection,
                    box=box.SIMPLE,
                    show_header=False,
                    show_lines=False,
                    padding=(0, 0, 0, 0))
                # columns
                notes_table.add_column(
                    "note",
                    style=self.style_infofield)
                notes_table.add_row(contact['notes'])

            # layout tables in a grid
            # banner and card info
            layout_1 = Table.grid()
            layout_1.add_column("single")
            layout_1.add_row(header_table)
            layout_1.add_row(record_table)
            # personal, business, email, phone,
            # messaging, and addresses
            layout_2 = Table.grid()
            if console.width >= 100:
                # two-column layout for terminal width >= 100
                layout_2.add_column("left", min_width=50)
                layout_2.add_column("right")

                # personal and business
                if ('personal_table' in locals() and
                        'business_table' in locals()):
                    layout_2.add_row(personal_table, business_table)
                elif 'personal_table' in locals():
                    layout_2.add_row(personal_table)
                elif 'business_table' in locals():
                    layout_2.add_row(business_table)

                # email and phone
                if ('email_table' in locals() and
                        'phone_table' in locals()):
                    layout_2.add_row(email_table, phone_table)
                elif 'email_table' in locals():
                    layout_2.add_row(email_table)
                elif 'phone_table' in locals():
                    layout_2.add_row(phone_table)

                # messaging and address
                if ('messaging_table' in locals() and
                        'addresses_table' in locals()):
                    layout_2.add_row(messaging_table, addresses_table)
                elif 'messaging_table' in locals():
                    layout_2.add_row(messaging_table)
                elif 'addresses_table' in locals():
                    layout_2.add_row(addresses_table)

            else:
                # single-column layout for terminal width <100
                layout_2.add_column("single")
                # personal
                if 'personal_table' in locals():
                    layout_2.add_row(personal_table)
                # business
                if 'business_table' in locals():
                    layout_2.add_row(business_table)
                # email
                if 'email_table' in locals():
                    layout_2.add_row(email_table)
                # phone
                if 'phone_table' in locals():
                    layout_2.add_row(phone_table)
                # messaging
                if 'messaging_table' in locals():
                    layout_2.add_row(messaging_table)
                # addresses
                if 'addresses_table' in locals():
                    layout_2.add_row(addresses_table)

            # websites, calendar, pgp keys, photo, and notes
            layout_3 = Table.grid()
            layout_3.add_column("single")
            if 'websites_table' in locals():
                layout_3.add_row(websites_table)
            if 'pgpkeys_table' in locals():
                layout_3.add_row(pgpkeys_table)
            if 'misc_table' in locals():
                layout_3.add_row(misc_table)
            if 'calendar_table' in locals():
                layout_3.add_row(calendar_table)
            if 'notes_table' in locals():
                layout_3.add_row(notes_table)

            # render the output with a pager if --pager or -p
            if pager:
                if self.color_pager:
                    with console.pager(styles=True):
                        console.print(
                            layout_1,
                            layout_2,
                            layout_3)
                else:
                    with console.pager():
                        console.print(
                            layout_1,
                            layout_2,
                            layout_3)
            else:
                console.print(
                    layout_1,
                    layout_2,
                    layout_3)

    def list(self, view='normal', pager=False):
        """List summary of all contacts parsed from contact files.

        Args:
            view (str):     The list view.
            pager (bool):   Pipe output through console.pager.

        """
        fifouids = {}
        for uid in self.contacts:
            name = self.contacts[uid].get("display")
            if name:
                fifouids[uid] = name
        sortlist = sorted(fifouids.items(), key=lambda x: x[1])
        uids = dict(sortlist)

        view = view.lower()
        shownormal = True if view == "normal" else False
        showarchive = True if view == "all" else False
        showfavorite = True if view == "favorite" else False
        showsingle = True if view in self._get_aliases() else False

        if any([shownormal, showarchive, showfavorite, showsingle]):
            def _table_title(shown):
                if view == "all":
                    header = f"All contacts ({shown})"
                elif view == "favorite":
                    header = f"Favorite ({shown})"
                elif showsingle:
                    header = "Contact (1)"
                else:
                    header = f"Contacts ({shown})"
                return header

            console = Console()
            list_table = Table(
                show_header=True,
                show_lines=True,
                header_style=self.style_listheader,
                box=box.SIMPLE,
                title="",
                title_justify="left",
                title_style=self.style_listtitle)
            list_table.add_column(
                "Alias",
                style=self.style_listalias,
                no_wrap=True,
                overflow=None)
            list_table.add_column(
                "Name",
                style=self.style_listname,
                no_wrap=True,
                overflow=None)
            list_table.add_column(
                "Email",
                style=self.style_listemail,
                no_wrap=False,
                overflow="fold")
            list_table.add_column(
                "Phone",
                style=self.style_listphone,
                no_wrap=False,
                overflow="fold")
            list_table.add_column(
                "Tags",
                style=self.style_listtags,
                no_wrap=False,
                overflow="fold")
            shown = 0
            for uid in uids:
                show = True
                contact = self._parse_contact(uid)
                if showsingle:
                    if view != contact['alias']:
                        show = False
                if contact['tags']:
                    if not showarchive and 'archive' in contact['tags']:
                        show = False
                    if showfavorite and 'favorite' not in contact['tags']:
                        show = False
                else:
                    if showfavorite:
                        show = False
                if show:
                    shown += 1
                    if contact['emails']:
                        this_email = ""
                        for entry in contact['emails']:
                            e_email = entry.get("email")
                            e_primary = entry.get("primary")
                            if e_email and e_primary and self.color_bold:
                                this_email += f"[bold]{e_email}[/bold]\n"
                            elif e_email:
                                this_email += f"{e_email}\n"
                    else:
                        this_email = ""
                    if contact['phones']:
                        this_phone = ""
                        for entry in contact['phones']:
                            e_number = entry.get("number")
                            e_primary = entry.get("primary")
                            if e_number and e_primary and self.color_bold:
                                this_phone += (
                                        f"[bold]{e_number}[/bold]\n"
                                )
                            elif e_number:
                                this_phone += f"{e_number}\n"
                    else:
                        this_phone = ""
                    if contact['tags']:
                        tags = ','.join(contact['tags'])
                    else:
                        tags = ""
                    list_table.add_row(
                        contact['alias'],
                        contact['display'],
                        this_email.rstrip(),
                        this_phone.rstrip(),
                        tags)
            if shown == 0:
                list_table.show_header = False
                nonetxt = Text("None")
                nonetxt.stylize("not bold default")
                list_table.add_row(nonetxt)
            list_table.title = _table_title(shown)
            layout = Table.grid()
            layout.add_column("single")
            layout.add_row("")
            layout.add_row(list_table)

            # render the output with a pager if --pager or -p
            if pager:
                if self.color_pager:
                    with console.pager(styles=True):
                        console.print(layout)
                else:
                    with console.pager():
                        console.print(layout)
            else:
                console.print(layout)
        else:
            self._handle_error(f"'{view}' is not a valid alias or view")

    def modify(self,
               alias,
               new_alias=None,
               new_display=None,
               new_tags=None,
               new_first=None,
               new_last=None,
               new_nickname=None,
               new_birthday=None,
               new_anniversary=None,
               new_spouse=None,
               new_language=None,
               new_gender=None,
               new_company=None,
               new_title=None,
               new_division=None,
               new_manager=None,
               new_assistant=None,
               new_office=None,
               new_photo=None,
               new_calurl=None,
               new_fburl=None,
               new_notes=None,
               add_email=None,
               del_email=None,
               add_phone=None,
               del_phone=None,
               add_address=None,
               del_address=None,
               add_messaging=None,
               del_messaging=None,
               add_website=None,
               del_website=None,
               add_pgpkey=None,
               del_pgpkey=None):
        """Modify a contact using provided parameters.

        Args:
            alias (str):     contact alias being updated.
            new_alias (str): new contact alias.
            new_display (str): new contact display name.
            new_tags (str):  new contact tags.
            new_first (str): new contact first name.
            new_last (str):  new contact last name.
            new_nickname (str): new contact nickname.
            new_birthday (str): new contact birthday.
            new_anniversary (str): new contact anniversary.
            new_spouse (str): new contact spouse's name.
            new_language (str): new contact preferred language.
            new_gender (str): new contact gender.
            new_company (str): new contact company name.
            new_title (str): new contact business title.
            new_division (str): new contact business division.
            new_manager (str): new contact manager's name.
            new_assistant (str): new contact assistant's name.
            new_office (str): new contact business office name or location.
            new_photo (str): new contact photo URL.
            new_calurl (str): new contact calendar URL.
            new_fburl (str): new contact free/busy URL.
            new_notes (str): new notes on contact record.
            add_email (str): new email address to add to contact.
            del_email (str): email address to remove from contact.
            add_phone (str): new phone number to add to contact.
            del_phone (str): phone number to remove from contact.
            add_address (str): new address to add to contact.
            del_address (str): address to remove from contact.
            add_messaging (str): new messaging account to add to contact.
            del_messaging (str): messaging account to remove from contact.
            add_website (str): new website URL to add to contact.
            del_website (str): website URL to remove from contact.
            add_pgpkey (str): new PGP key URL to add to contact.
            del_pgpkey (str): PGP key URL to remove from contact.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)

        def _new_or_current(new, current):
            """Return a datetime obj for the new date (if existant and
            valid) or the current date (if existant) or None.
            Args:
                new (str):  the new timestring.
                current (obj): the current datetime object or None.
            Returns:
                updated (obj):  datetime or None.
            """
            if new:
                new = self._datetime_or_none(new)
                if new:
                    updated = new
                elif current:
                    updated = current
                else:
                    updated = None
            elif current:
                updated = current
            else:
                updated = None
            return updated

        def _remove_items(deletions, source):
            """Removes items (identified by index) from a list.

            Args:
                deletions (list):   the indexes to be deleted.
                source (list):    the list from which to remove.

            Returns:
                source (list):    the modified list.

            """
            rem_items = []
            for entry in deletions:
                try:
                    entry = int(entry)
                except ValueError:
                    pass
                else:
                    if 1 <= entry <= len(source):
                        entry -= 1
                        rem_items.append(source[entry])
            if rem_items:
                for item in rem_items:
                    source.remove(item)
            return source

        if not uid:
            self._alias_not_found(alias)
        else:
            filename = self.contact_files.get(uid)
            aliases = self._get_aliases()
            contact = self._parse_contact(uid)

            if filename:
                created = contact['created']
                u_updated = datetime.now(tz=self.ltz)
                # alias
                if new_alias:
                    new_alias = new_alias.lower()
                    # duplicate alias check
                    aliases = self._get_aliases()
                    msg = f"alias '{alias}' already exists"
                    if new_alias in aliases and self.interactive:
                        self._error_pass(msg)
                        return
                    elif new_alias in aliases:
                        self._error_exit(msg)
                    else:
                        u_alias = new_alias
                else:
                    u_alias = alias
                # display name
                u_display = new_display or contact['display']
                # first name
                u_first = new_first or contact['first']
                # last name
                u_last = new_last or contact['last']
                # nickname
                u_nickname = new_nickname or contact['nickname']
                # tags
                if new_tags:
                    new_tags = new_tags.lower()
                    if new_tags.startswith('+'):
                        new_tags = new_tags[1:]
                        new_tags = new_tags.split(',')
                        if not contact['tags']:
                            tags = []
                        else:
                            tags = contact['tags'].copy()
                        for new_tag in new_tags:
                            if new_tag not in tags:
                                tags.append(new_tag)
                        if tags:
                            tags.sort()
                            u_tags = tags
                        else:
                            u_tags = None
                    elif new_tags.startswith('~'):
                        new_tags = new_tags[1:]
                        new_tags = new_tags.split(',')
                        if contact['tags']:
                            tags = contact['tags'].copy()
                            for new_tag in new_tags:
                                if new_tag in tags:
                                    tags.remove(new_tag)
                            if tags:
                                tags.sort()
                                u_tags = tags
                            else:
                                u_tags = None
                        else:
                            u_tags = None
                    else:
                        u_tags = new_tags.split(',')
                        u_tags.sort()
                else:
                    u_tags = contact['tags']
                # birthday
                if new_birthday:
                    u_birthday = _new_or_current(
                            new_birthday, contact['birthday'])
                else:
                    u_birthday = contact['birthday']
                # anniversary
                if new_anniversary:
                    u_anniversary = _new_or_current(
                            new_anniversary, contact['anniversary'])
                else:
                    u_anniversary = contact['anniversary']
                # spouse
                u_spouse = new_spouse or contact['spouse']
                # language
                u_language = new_language or contact['language']
                # gender
                u_gender = new_gender or contact['gender']
                # company
                u_company = new_company or contact['company']
                # title
                u_title = new_title or contact['title']
                # division
                u_division = new_division or contact['division']
                # manager
                u_manager = new_manager or contact['manager']
                # assistant
                u_assistant = new_assistant or contact['assistant']
                # office
                u_office = new_office or contact['office']
                # calendar URL
                u_calurl = new_calurl or contact['calurl']
                # free/busy URL
                u_fburl = new_fburl or contact['fburl']
                # photo URL
                u_photo = new_photo or contact['photo']
                # notes
                if new_notes:
                    # the new note is functionally empty or is using a
                    # placeholder from notes() to clear the notes
                    if new_notes in [' ', ' \n', '\n']:
                        u_notes = None
                    else:
                        u_notes = new_notes
                else:
                    u_notes = contact['notes']
                # emails
                if add_email or del_email:
                    if contact['emails']:
                        u_emails = contact['emails'].copy()
                    else:
                        u_emails = []
                    if del_email and u_emails:
                        u_emails = _remove_items(del_email, u_emails)
                    if add_email:
                        for entry in add_email:
                            this_entry = self._parse_entry("email", entry)
                            u_emails.append(this_entry)
                    if not u_emails:
                        u_emails = None
                else:
                    u_emails = contact['emails']
                # phones
                if add_phone or del_phone:
                    if contact['phones']:
                        u_phones = contact['phones'].copy()
                    else:
                        u_phones = []
                    if del_phone and u_phones:
                        u_phones = _remove_items(del_phone, u_phones)
                    if add_phone:
                        for entry in add_phone:
                            this_entry = self._parse_entry("number", entry)
                            u_phones.append(this_entry)
                    if not u_phones:
                        u_phones = None
                else:
                    u_phones = contact['phones']
                # messaging accounts
                if add_messaging or del_messaging:
                    if contact['messaging']:
                        u_messaging = contact['messaging'].copy()
                    else:
                        u_messaging = []
                    if del_messaging and u_messaging:
                        u_messaging = _remove_items(del_messaging, u_messaging)
                    if add_messaging:
                        for entry in add_messaging:
                            this_entry = self._parse_entry("account", entry)
                            u_messaging.append(this_entry)
                    if not u_messaging:
                        u_messaging = None
                else:
                    u_messaging = contact['messaging']
                # addresses
                if add_address or del_address:
                    if contact['addresses']:
                        u_addresses = contact['addresses'].copy()
                    else:
                        u_addresses = []
                    if del_address and u_addresses:
                        u_addresses = _remove_items(del_address, u_addresses)
                    if add_address:
                        for address in add_address:
                            this_address = self._parse_address(address)
                            if this_address:
                                u_addresses.append(this_address)
                    if not u_addresses:
                        u_addresses = None
                else:
                    u_addresses = contact['addresses']
                # website URLs
                if add_website or del_website:
                    if contact['websites']:
                        u_websites = contact['websites'].copy()
                    else:
                        u_websites = []
                    if del_website and u_websites:
                        u_websites = _remove_items(del_website, u_websites)
                    if add_website:
                        for entry in add_website:
                            this_entry = self._parse_entry("url", entry)
                            u_websites.append(this_entry)
                    if not u_websites:
                        u_websites = None
                else:
                    u_websites = contact['websites']
                # PGP key URLs
                if add_pgpkey or del_pgpkey:
                    if contact['pgpkeys']:
                        u_pgpkeys = contact['pgpkeys'].copy()
                    else:
                        u_pgpkeys = []
                    if del_pgpkey and u_pgpkeys:
                        u_pgpkeys = _remove_items(del_pgpkey, u_pgpkeys)
                    if add_pgpkey:
                        for entry in add_pgpkey:
                            this_entry = self._parse_entry("url", entry)
                            u_pgpkeys.append(this_entry)
                    if not u_pgpkeys:
                        u_pgpkeys = None
                else:
                    u_pgpkeys = contact['pgpkeys']

                data = {
                    "contact": {
                        "uid": uid,
                        "created": created,
                        "updated": u_updated,
                        "alias": u_alias,
                        "tags": u_tags,
                        "display": u_display,
                        "first": u_first,
                        "last": u_last,
                        "nickname": u_nickname,
                        "birthday": u_birthday,
                        "anniversary": u_anniversary,
                        "spouse": u_spouse,
                        "language": u_language,
                        "gender": u_gender,
                        "company": u_company,
                        "title": u_title,
                        "division": u_division,
                        "manager": u_manager,
                        "assistant": u_assistant,
                        "office": u_office,
                        "calurl": u_calurl,
                        "fburl": u_fburl,
                        "photo": u_photo,
                        "emails": u_emails,
                        "phones": u_phones,
                        "messaging": u_messaging,
                        "addresses": u_addresses,
                        "websites": u_websites,
                        "pgpkeys": u_pgpkeys,
                        "notes": u_notes
                    }
                }
                # write the updated file
                self._write_yaml_file(data, filename)

    def mutt(self, term):
        """Search for contact display names and email addresses and
        and output in a format compatible with the `query_command`
        used by mutt/neomutt for address completion.

        Search rules for mutt/neomutt query:
        1. On an exact match for the alias, provide the primary email
           address or the first email address if no primary;
        2. Otherwise send all names and email addresses that match
           the search term.

        Args:
            term (str):    The information for which to search and
        match against either display name, alias, and/or email address.

        """
        search = term.lower()
        for uid in self.contacts:
            contact = self._parse_contact(uid)
            if contact['alias']:
                if search == contact['alias']:
                    this_email = None
                    if contact['emails']:
                        for entry in contact['emails']:
                            if entry.get("primary"):
                                this_email = entry.get("email")
                        if not this_email:
                            this_email = contact['emails'][0].get("email")
                    if this_email:
                        print("Found alias match:")
                        print(
                            f"{this_email}\t{contact['display']}\t"
                            f"{contact['alias']}"
                        )
                    return

        matches = []
        for uid in self.contacts:
            contact = self._parse_contact(uid)
            if contact['emails']:
                for entry in contact['emails']:
                    this_email = entry.get("email")
                    if (this_email and
                            contact['display'] and
                            contact['alias']):
                        if (search in this_email.lower() or
                                search in contact['display'].lower()):
                            matches.append(
                                f"{this_email}\t{contact['display']}\t"
                                f"{contact['alias']}"
                            )
        if matches:
            count = len(matches)
            print(f"Found {count} matches:")
            for match in matches:
                print(match)
        else:
            print("No matches.")
            sys.exit(1)

    def new(self,
            alias=None,
            display=None,
            tags=None,
            first=None,
            last=None,
            nickname=None,
            birthday=None,
            anniversary=None,
            spouse=None,
            language=None,
            gender=None,
            company=None,
            title=None,
            division=None,
            manager=None,
            assistant=None,
            office=None,
            photo=None,
            calurl=None,
            fburl=None,
            notes=None,
            emails=None,
            phones=None,
            addresses=None,
            messaging=None,
            websites=None,
            pgpkeys=None):
        """Create a new contact.

        Args:
            alias (str):    a custom alias to use for the new contact.
            display (str):  the contact display name.
            tags (str):     tags assigned to the contact.
            first (str):    contact first name.
            last (str):     contact last name.
            nickname (str): contact nickname.
            birthday (str): contact birthday (YYYY-MM-DD)
            anniversary (str): contact's anniversary (YYYY-MM-DD)
            spouse (str):   contact spouse's name.
            language (str): contact preferred language.
            gender (str):   contact gender.
            company (str):  contact company name.
            title (str):    contact title.
            division (str): contact business division.
            manager (str):  contact manager name.
            assistant (str): contact assistant name.
            office (str):   contact office location.
            photo (str):    contact photo location (url).
            calurl (str):   contact calendar location (url).
            fburl (str):    contact free/busy location (url).
            notes (str):    contact notes.
            emails (lst):   contact email addresses.
            phones (lst):   contact phone numbers.
            addresses (lst): contact physical/postal addresses.
            messaging (lst): contact messaging accounts.
            websites (lst): contact websites.
            pgpkeys (lst):  contact PGP keys.

        """
        uid = str(uuid.uuid4())
        created = datetime.now(tz=self.ltz)
        updated = created
        if alias:
            alias = alias.lower()
            # duplicate alias check
            aliases = self._get_aliases()
            msg = f"alias '{alias}' already exists"
            if alias in aliases and self.interactive:
                self._error_pass(msg)
                return
            elif alias in aliases:
                self._error_exit(msg)
        else:
            alias = self._gen_alias()
        display = display or "New contact"
        if tags:
            tags = tags.lower()
            tags = tags.split(',')
            tags.sort()
        filename = os.path.join(self.data_dir, f'{uid}.yml')
        # emails
        if emails:
            new_emails = []
            for entry in emails:
                this_entry = self._parse_entry("email", entry)
                new_emails.append(this_entry)
        else:
            new_emails = None
        # phones
        if phones:
            new_phones = []
            for entry in phones:
                this_entry = self._parse_entry("number", entry)
                new_phones.append(this_entry)
        else:
            new_phones = None
        # messaging
        if messaging:
            new_messaging = []
            for entry in messaging:
                this_entry = self._parse_entry("account", entry)
                new_messaging.append(this_entry)
        else:
            new_messaging = None
        # addresses
        if addresses:
            new_addresses = []
            for address in addresses:
                this_address = self._parse_address(address)
                if this_address:
                    new_addresses.append(this_address)
        else:
            new_addresses = None
        # websites
        if websites:
            new_websites = []
            for entry in websites:
                this_entry = self._parse_entry("url", entry)
                new_websites.append(this_entry)
        else:
            new_websites = None
        # pgpkeys
        if pgpkeys:
            new_pgpkeys = []
            for entry in pgpkeys:
                this_entry = self._parse_entry("url", entry)
                new_pgpkeys.append(this_entry)
        else:
            new_pgpkeys = None

        data = {
            "contact": {
                "uid": uid,
                "created": created,
                "updated": updated,
                "alias": alias,
                "tags": tags,
                "display": display,
                "first": first,
                "last": last,
                "nickname": nickname,
                "birthday": birthday,
                "anniversary": anniversary,
                "spouse": spouse,
                "language": language,
                "gender": gender,
                "company": company,
                "title": title,
                "division": division,
                "manager": manager,
                "assistant": assistant,
                "office": office,
                "calurl": calurl,
                "fburl": fburl,
                "photo": photo,
                "emails": new_emails,
                "phones": new_phones,
                "messaging": new_messaging,
                "addresses": new_addresses,
                "websites": new_websites,
                "pgpkeys": new_pgpkeys,
                "notes": notes
            }
        }
        # write the new file
        self._write_yaml_file(data, filename)
        print(f"Added contact: {alias}")

    def new_contact_wizard(self):
        """Prompt the user for contact parameters and then call new()."""
        new_alias = self._gen_alias()
        aliases = self._get_aliases()

        def _ask_alias():
            """Asks for an alias for a new contact and checks for
            duplication with existing contacts.

            Returns:
                alias (str):    the new contact alias.

            """
            alias = input(f"Alias [{new_alias}]: ").lower() or new_alias
            while alias in aliases:
                self._error_pass(f"Alias '{alias}' already in use")
                alias = _ask_alias()
            return alias

        alias = _ask_alias()
        display = input("Display name [New contact]: ") or "New contact"
        tags = input("Tags [none]: ") or None
        personal = input("Add personal info? [N/y]: ").lower()
        if personal in ['y', 'yes']:
            first = input("First name []: ") or None
            last = input("Last name []: ") or None
            nickname = input("Nickname []: ") or None
            birthday = input("Birthday (YYYY-MM-DD) []: ") or None
            if birthday:
                birthday = self._datetime_or_none(birthday)
            anniversary = input("Anniversary (YYYY-MM-DD) []: ") or None
            if anniversary:
                anniversary = self._datetime_or_none(anniversary)
            spouse = input("Spouse []: ") or None
            language = input("Language []: ") or None
            gender = input("Gender []: ") or None
        else:
            first = None
            last = None
            nickname = None
            birthday = None
            anniversary = None
            spouse = None
            language = None
            gender = None
        business = input("Add business info? [N/y]: ").lower()
        if business in ['y', 'yes']:
            company = input("Company name []: ") or None
            title = input("Title []: ") or None
            division = input("Division []: ") or None
            manager = input("Manager's name []: ") or None
            assistant = input("Assistant's name []: ") or None
            office = input("Office name/location []: ") or None
        else:
            company = None
            title = None
            division = None
            manager = None
            assistant = None
            office = None
        other = input("Other fields? [N/y]: ").lower()
        if other in ['y', 'yes']:
            photo = input("Photo URL []: ") or None
            calurl = input("Calendar URL []: ") or None
            fburl = input("Free/busy URL []: ") or None
        else:
            photo = None
            calurl = None
            fburl = None

        add_email = input("Add email address(es)? [N/y]: ").lower()
        if add_email in ['y', 'yes']:
            self.add_new_email()
        else:
            self.add_emails = None

        add_phone = input("Add phone number(s)? [N/y]: ").lower()
        if add_phone in ['y', 'yes']:
            self.add_new_phone()
        else:
            self.add_phones = None

        add_messaging = input("Add messaging account(s)? [N/y]: ").lower()
        if add_messaging in ['y', 'yes']:
            self.add_new_messaging()
        else:
            self.add_messaging = None

        add_address = input("Add physical/postal address(es)? [N/y]: ").lower()
        if add_address in ['y', 'yes']:
            self.add_new_address()
        else:
            self.add_addresses = None

        add_website = input("Add website(s)? [N/y]: ").lower()
        if add_website in ['y', 'yes']:
            self.add_new_website()
        else:
            self.add_websites = None

        add_pgpkey = input("Add PGP key(s)? [N/y]: ").lower()
        if add_pgpkey in ['y', 'yes']:
            self.add_new_pgpkey()
        else:
            self.add_pgpkeys = None

        self.new(
            alias=alias,
            display=display,
            tags=tags,
            first=first,
            last=last,
            nickname=nickname,
            birthday=birthday,
            anniversary=anniversary,
            spouse=spouse,
            language=language,
            gender=gender,
            company=company,
            title=title,
            division=division,
            manager=manager,
            assistant=assistant,
            office=office,
            photo=photo,
            calurl=calurl,
            fburl=fburl,
            notes=None,
            emails=self.add_emails,
            phones=self.add_phones,
            addresses=self.add_addresses,
            messaging=self.add_messaging,
            websites=self.add_websites,
            pgpkeys=self.add_pgpkeys)

        # reset
        self.add_emails = None
        self.add_phones = None
        self.add_addresses = None
        self.add_messaging = None
        self.add_websites = None
        self.add_pgpkeys = None

    def notes(self, alias):
        """Adds or updates notes on a contact.
        Args:
            alias (str):        the contact alias being updated.
        """
        if self.editor:
            uid = self._uid_from_alias(alias)
            if not uid:
                self._alias_not_found(alias)
            else:
                contact = self._parse_contact(uid)
                if not contact['notes']:
                    fnotes = ""
                else:
                    fnotes = contact['notes']
                handle, abs_path = tempfile.mkstemp()
                with os.fdopen(handle, 'w') as temp_file:
                    temp_file.write(fnotes)

                # open the tempfile in $EDITOR and then update the contact
                # with the new note
                try:
                    subprocess.run([self.editor, abs_path], check=True)
                    with open(abs_path, "r",
                              encoding="utf-8") as temp_file:
                        new_note = temp_file.read()
                except subprocess.SubprocessError:
                    msg = "failure editing note"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
                else:
                    # notes were deleted entirely but if we set this to
                    # None then the note won't be updated. Set it to " "
                    # and then use special handling in modify()
                    if contact['notes'] and not new_note:
                        new_note = " "
                    self.modify(
                        alias=alias,
                        new_notes=new_note)
                    os.remove(abs_path)
        else:
            self._handle_error("$EDITOR is required and not set")

    def query(self, term, limit=False, json_output=False):
        """Search contacts by email address, phone number, alias,
        name, tag, address, birthday, anniversary or any. Print results
        in tab-delimited plain text or JSON.
        Optionally, limit output to a specific field or fields based
        on --limit.

        A 'term' can consist of two parts: 'search' and 'exclude'. The
        operator '%' separates the two parts. The 'exclude' part is
        optional.
        The 'search' and 'exclude' terms use the same syntax but differ
        in one noteable way:
          - 'search' is parsed as AND. All parameters must match to
        return a contact record. Note that within a parameter the '+'
        operator is still an OR.
          - 'exclude' is parsed as OR. Any parameters that match will
        exclude a contact record.

        Args:
            term (str):     the search term of contacts to output.
            limit (str or list):  Filter output to specific fields.
            json_output (bool): output in JSON format.

        """
        results = self._perform_search(term)

        if limit:
            limit = limit.split(',')

        contacts_out = {}
        contacts_out['contacts'] = []
        text_out = ""
        if len(results) > 0:
            for uid in results:
                this_contact = {}
                contact = self._parse_contact(uid)
                alias = contact['alias'] or ""
                display = contact['display'] or ""
                tags = contact['tags'] or []
                created = contact['created']
                updated = contact['updated']
                if created:
                    created = self._format_timestamp(created)
                if updated:
                    updated = self._format_timestamp(updated)
                if contact['birthday']:
                    birthday = self._format_timestamp(
                            contact['birthday'], True)
                    j_birthday = self._format_timestamp(
                            contact['birthday'])
                else:
                    birthday = ""
                    j_birthday = None
                if contact['anniversary']:
                    anniversary = self._format_timestamp(
                            contact['anniversary'], True)
                    j_anniversary = self._format_timestamp(
                            contact['anniversary'])
                else:
                    anniversary = ""
                    j_anniversary = None
                lstemail = []
                lstphone = []
                lstaddress = []
                if contact['emails']:
                    for entry in contact['emails']:
                        e_email = entry.get("email")
                        e_primary = entry.get("primary")

                        if limit:
                            if (e_email and
                                    e_primary and
                                    "email:primary" in limit):
                                lstemail.append(e_email)
                            elif e_email and "email:primary" not in limit:
                                lstemail.append(e_email)
                        else:
                            lstemail.append(e_email)

                if contact['phones']:
                    for entry in contact['phones']:
                        e_number = entry.get("number")
                        e_primary = entry.get("primary")

                        if limit:
                            if (e_number and
                                    e_primary and
                                    "phone:primary" in limit):
                                lstphone.append(e_number)
                            elif e_number and "phone:primary" not in limit:
                                lstphone.append(e_number)
                        else:
                            lstphone.append(e_number)

                if contact['addresses']:
                    for entry in contact['addresses']:
                        e_primary = entry.get("primary")
                        empty = True
                        this_address = []
                        this_address.append(str(entry.get('address1')))
                        this_address.append(str(entry.get('address2')))
                        this_address.append(str(entry.get('city')))
                        this_address.append(str(entry.get('state')))
                        this_address.append(str(entry.get('zipcode')))
                        this_address.append(str(entry.get('country')))
                        for item in this_address:
                            if item != "None":
                                empty = False
                        if not empty:
                            if limit:
                                if (this_address and e_primary and
                                   "address:primary" in limit):
                                    this_address = ['' if i == "None"
                                                    else i for i
                                                    in this_address]
                                    lstaddress.append(
                                        ';'.join(this_address))
                                elif (this_address and
                                      "address:primary" not in limit):
                                    this_address = ['' if i == "None"
                                                    else i for i
                                                    in this_address]
                                    lstaddress.append(
                                        ';'.join(this_address))
                            else:
                                this_address = ['' if i == "None"
                                                else i for i
                                                in this_address]
                                lstaddress.append(
                                    ';'.join(this_address))

                if limit:
                    output = ""
                    if "uid" in limit:
                        output += f"{uid}\t"
                    if "alias" in limit:
                        output += f"{alias}\t"
                    if "name" in limit:
                        output += f"{display}\t"
                    if "email" in limit or "email:primary" in limit:
                        output += f"{lstemail}\t"
                    if "phone" in limit or "phone:primary" in limit:
                        output += f"{lstphone}\t"
                    if "address" in limit or "address:primary" in limit:
                        output += f"{lstaddress}\t"
                    if "birthday" in limit:
                        output += f"{birthday}\t"
                    if "anniversary" in limit:
                        output += f"{anniversary}\t"
                    if "tags" in limit:
                        output += f"{tags}\t"
                    if output.endswith('\t'):
                        output = output.rstrip(output[-1])
                    output = f"{output}\n"
                else:
                    output = (
                        f"{uid}\t"
                        f"{alias}\t"
                        f"{display}\t"
                        f"{lstemail}\t"
                        f"{lstphone}\t"
                        f"{lstaddress}\t"
                        f"{birthday}\t"
                        f"{anniversary}\t"
                        f"{tags}\n"
                    )
                this_contact['uid'] = uid
                this_contact['created'] = created
                this_contact['updated'] = updated
                this_contact['alias'] = contact['alias']
                this_contact['display'] = contact['display']
                this_contact['first'] = contact['first']
                this_contact['last'] = contact['last']
                this_contact['nickname'] = contact['nickname']
                this_contact['birthday'] = j_birthday
                this_contact['anniversary'] = j_anniversary
                this_contact['spouse'] = contact['spouse']
                this_contact['language'] = contact['language']
                this_contact['gender'] = contact['gender']
                this_contact['company'] = contact['company']
                this_contact['title'] = contact['title']
                this_contact['division'] = contact['division']
                this_contact['department'] = contact['department']
                this_contact['office'] = contact['office']
                this_contact['manager'] = contact['manager']
                this_contact['assistant'] = contact['assistant']
                this_contact['calurl'] = contact['calurl']
                this_contact['fburl'] = contact['fburl']
                this_contact['photo'] = contact['photo']
                this_contact['tags'] = contact['tags']
                this_contact['emails'] = contact['emails']
                this_contact['phones'] = contact['phones']
                this_contact['messaging'] = contact['messaging']
                this_contact['addresses'] = contact['addresses']
                this_contact['websites'] = contact['websites']
                this_contact['pgpkeys'] = contact['pgpkeys']
                this_contact['notes'] = contact['notes']
                contacts_out['contacts'].append(this_contact)
                text_out += f"{output}"
        if json_output:
            json_out = json.dumps(contacts_out, indent=4)
            print(json_out)
        else:
            if text_out != "":
                print(text_out, end="")
            else:
                print("No results.")

    def refresh(self):
        """Public method to refresh data."""
        self._parse_files()

    def search(self, term, pager=False):
        """Search contacts by email address, phone number, alias,
        name, tag, address, or any.

        A 'term' can consist of two parts: 'search' and 'exclude'. The
        operator '%' separates the two parts. The 'exclude' part is
        optional.
        The 'search' and 'exclude' terms use the same syntax but differ
        in one noteable way:
          - 'search' is parsed as AND. All parameters must match to
        return a contact record. Note that within a parameter the '+'
        operator is still an OR.
          - 'exclude' is parsed as OR. Any parameters that match will
        exclude a contact record.

        Args:
            term (str):     the search term of contacts to view.
            pager (bool):   Pipe output through console.pager.

        """
        results = self._perform_search(term)

        if len(results) > 0:
            fifouids = {}
            for uid in results:
                name = self.contacts[uid].get("display")
                if name:
                    fifouids[uid] = name
            sortlist = sorted(fifouids.items(), key=lambda x: x[1])
            uids = dict(sortlist)

            console = Console()
            search_table = Table(
                show_header=True,
                show_lines=True,
                header_style=self.style_listheader,
                box=box.SIMPLE,
                title=f"Search results ({len(results)})",
                title_justify="left",
                title_style=self.style_listtitle)
            search_table.add_column(
                "Alias",
                style=self.style_listalias,
                no_wrap=True,
                overflow=None)
            search_table.add_column(
                "Name",
                style=self.style_listname,
                no_wrap=True,
                overflow=None)
            search_table.add_column(
                "Email",
                style=self.style_listemail,
                no_wrap=False,
                overflow="fold")
            search_table.add_column(
                "Phone",
                style=self.style_listphone,
                no_wrap=False,
                overflow="fold")
            search_table.add_column(
                "Tags",
                style=self.style_listtags,
                no_wrap=False,
                overflow="fold")
            for uid in uids:
                contact = self._parse_contact(uid)
                this_email = None
                phone = None
                if contact['emails']:
                    this_email = ""
                    for entry in contact['emails']:
                        e_email = entry.get("email")
                        e_primary = entry.get("primary")
                        if e_email and e_primary and self.color_bold:
                            this_email += f"[bold]{str(e_email)}[/bold]\n"
                        elif e_email:
                            this_email += f"{str(e_email)}\n"
                if not this_email:
                    this_email = ""
                if contact['phones']:
                    phone = ""
                    for entry in contact['phones']:
                        e_number = entry.get("number")
                        e_primary = entry.get("primary")
                        if e_number and e_primary and self.color_bold:
                            phone += f"[bold]{str(e_number)}[/bold]\n"
                        elif e_number:
                            phone += f"{str(e_number)}\n"
                if not phone:
                    phone = ""
                if contact['tags']:
                    tags = ','.join(contact['tags'])
                else:
                    tags = ""
                search_table.add_row(
                    contact['alias'],
                    contact['display'],
                    this_email.rstrip(),
                    phone.rstrip(),
                    tags)

            layout = Table.grid()
            layout.add_column("single")
            layout.add_row("")
            layout.add_row(search_table)

            # render the output with a pager if --pager or -p
            if pager:
                if self.color_pager:
                    with console.pager(styles=True):
                        console.print(layout)
                else:
                    with console.pager():
                        console.print(layout)
            else:
                console.print(layout)
        else:
            print("No results.")

    def unset(self, alias, field):
        """Clear a specified field for a given alias.

        Args:
            alias (str):    the contact alias.
            field (str):    the field to clear.

        """
        alias = alias.lower()
        field = field.lower()
        # friendly name conversion
        if field == 'calendar':
            field = 'calurl'
        elif field == 'freebusy':
            field = 'fburl'
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            allowed_fields = [
                'tags',
                'first',
                'last',
                'nickname',
                'birthday',
                'anniversary',
                'spouse',
                'language',
                'gender',
                'company',
                'title',
                'division',
                'manager',
                'assistant',
                'office',
                'photo',
                'calurl',
                'fburl'
            ]
            if field in allowed_fields:
                if self.contacts[uid][field]:
                    self.contacts[uid][field] = None
                    contact = self._parse_contact(uid)
                    filename = self.contact_files.get(uid)
                    if contact and filename:
                        data = {
                            "contact": {
                                "uid": contact['uid'],
                                "created": contact['created'],
                                "updated": contact['updated'],
                                "alias": contact['alias'],
                                "tags": contact['tags'],
                                "display": contact['display'],
                                "first": contact['first'],
                                "last": contact['last'],
                                "nickname": contact['nickname'],
                                "birthday": contact['birthday'],
                                "anniversary": contact['anniversary'],
                                "spouse": contact['spouse'],
                                "language": contact['language'],
                                "gender": contact['gender'],
                                "company": contact['company'],
                                "title": contact['title'],
                                "division": contact['division'],
                                "manager": contact['manager'],
                                "assistant": contact['assistant'],
                                "office": contact['office'],
                                "calurl": contact['calurl'],
                                "fburl": contact['fburl'],
                                "photo": contact['photo'],
                                "emails": contact['emails'],
                                "phones": contact['phones'],
                                "messaging": contact['messaging'],
                                "addresses": contact['addresses'],
                                "websites": contact['websites'],
                                "pgpkeys": contact['pgpkeys'],
                                "notes": contact['notes']
                            }
                        }
                        # write the updated file
                        self._write_yaml_file(data, filename)
            else:
                self._handle_error(f"cannot clear field '{field}'")


class FSHandler(FileSystemEventHandler):
    """Handler to watch for file changes and refresh data from files.

    Attributes:
        shell (obj):    the calling shell object.

    """
    def __init__(self, shell):
        """Initializes an FSHandler() object."""
        self.shell = shell

    def on_any_event(self, event):
        """Refresh data in memory on data file changes.

        Args:
            event (obj):    file system event.

        """
        if event.event_type in [
                'created', 'modified', 'deleted', 'moved']:
            self.shell.do_refresh("silent")


class ContactsShell(Cmd):
    """Provides methods for interactive shell use.

    Attributes:
        contacts (obj):     an instance of Contacts().

    """
    def __init__(
            self,
            contacts,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes a ContactsShell() object."""
        super().__init__()
        self.contacts = contacts

        # start watchdog for data_dir changes
        # and perform refresh() on changes
        observer = Observer()
        handler = FSHandler(self)
        observer.schedule(
                handler,
                self.contacts.data_dir,
                recursive=True)
        observer.start()

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )
        self.do_clear(None)

        print(
            f"{APP_NAME} {APP_VERS}\n\n"
            f"Enter command (or 'help')\n"
        )

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args == "quit":
            self.do_exit("")
        elif args.startswith("lsa"):
            newargs = args.split()
            newargs[0] = "all"
            self.do_list(' '.join(newargs))
        elif args.startswith("lsf"):
            newargs = args.split()
            newargs[0] = "favorite"
            self.do_list(' '.join(newargs))
        elif args.startswith("ls"):
            newargs = args.split(' ')
            if len(newargs) > 1:
                self.do_list(' '.join(newargs[1:]))
            else:
                self.do_list("")
        elif args.startswith("rm"):
            newargs = args.split(' ')
            if len(newargs) > 1:
                self.do_delete(' '.join(newargs[1:]))
            else:
                self.do_delete("")
        elif args.startswith("mod"):
            newargs = args.split(' ')
            if len(newargs) > 1:
                self.do_modify(' '.join(newargs[1:]))
            else:
                self.do_modify("")
        else:
            print("\nNo such command. See 'help'.\n")

    def emptyline(self):
        """Ignore empty line entry."""

    def _set_prompt(self):
        """Set the prompt string."""
        if self.contacts.color_bold:
            self.prompt = "\033[1mcontacts\033[0m> "
        else:
            self.prompt = "contacts> "

    def _uid_from_alias(self, alias):
        """Get the uid for a valid alias.

        Args:
            alias (str):    The alias of the task for which to find uid.

        Returns:
            uid (str or None): The uid that matches the submitted alias.

        """
        alias = alias.lower()
        uid = None
        for contact in self.contacts.contacts:
            this_alias = self.contacts.contacts[contact].get("alias")
            if this_alias:
                if this_alias == alias:
                    uid = contact
        return uid

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_config(self, args):
        """Edit the config file and reload the configuration.

        Args:
            args (str): the command arguments, ignored.

        """
        self.contacts.edit_config()

    def do_delete(self, args):
        """Delete a contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            term = str(commands[0]).lower()
            self.contacts.delete(term)
        else:
            self.help_delete()

    def do_edit(self, args):
        """Edit a contact via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            term = str(commands[0]).lower()
            self.contacts.edit(term)
        else:
            self.help_edit()

    @staticmethod
    def do_exit(args):
        """Exit the contacts shell.

        Args:
            args (str): the command arguments, ignored.

        """
        sys.exit(0)

    def do_export(self, args):
        """Search for contact(s) and export to a vCard 4.0 file.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if len(commands) == 2:
                term = str(commands[0]).lower()
                filename = str(commands[1])
                self.contacts.export(term, filename)
            else:
                self.help_export()
        else:
            self.help_export()

    def do_info(self, args):
        """Display full details for a contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            term = str(commands[0]).lower()
            if len(commands) > 1:
                if str(commands[1]) == "|":
                    self.contacts.info(term, True)
                else:
                    self.contacts.info(term)
            else:
                self.contacts.info(term)
        else:
            self.help_info()

    def do_list(self, args):
        """Output a list of all contacts (except archive).

        Args:
            args (str): the command arguments, ignored.

        """
        if len(args) > 0:
            args = args.strip()
            pager = False
            if args.endswith('|'):
                pager = True
                args = args[:-1].strip()
            commands = args.split()
            if len(commands) > 0:
                view = str(commands[0]).lower()
            else:
                view = 'normal'
            self.contacts.list(view, pager)
        else:
            self.contacts.list()

    def do_modify(self, args):
        """Modify a contact.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            alias = str(commands[0]).lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                print(f"Alias '{alias}' not found")
            else:
                subshell = ModShell(self.contacts, uid, alias)
                subshell.cmdloop()
        else:
            self.help_modify()

    def do_new(self, args):
        """Evoke the new contact wizard.

        Args:
            args (str): the command arguments, ignored.

        """
        try:
            self.contacts.new_contact_wizard()
        except KeyboardInterrupt:
            print("\nCancelled.")

    def do_notes(self, args):
        """Edit contact notes via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.contacts.notes(str(commands[0]).lower())
        else:
            self.help_notes()

    def do_refresh(self, args):
        """Refresh contact information if files changed on disk.

        Args:
            args (str): the command arguments, ignored.

        """
        self.contacts.refresh()
        if args != "silent":
            print("Data refreshed.")

    def do_search(self, args):
        """Search for contact(s) and output a list of results.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            term = str(args).strip()
            if term.endswith('|'):
                term = term[:-1].strip()
                page = True
            else:
                page = False
            self.contacts.search(term, page)
        else:
            self.help_search()

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_config():
        """Output help for 'config' command."""
        print(
            '\nconfig:\n'
            '    Edit the config file with $EDITOR and then reload '
            'the configuration and refresh data files.\n'
        )

    @staticmethod
    def help_delete():
        """Output help for 'delete' command."""
        print(
            '\ndelete (rm) <alias>:\n'
            '    Delete a contact file.\n'
        )

    @staticmethod
    def help_edit():
        """Output help for 'edit' command."""
        print(
            '\nedit <alias>:\n'
            '    Edit a contact file with $EDITOR.\n'
        )

    @staticmethod
    def help_export():
        """Output help for 'export' command."""
        print(
            '\nexport <term> <file>:\n'
            '    Perform a search and export the results to a file '
            'in vCard 4.0 format.\n'
        )

    @staticmethod
    def help_exit():
        """Output help for 'exit' command."""
        print(
            '\nexit:\n'
            '    Exit the contacts shell.\n'
        )

    @staticmethod
    def help_help():
        """Output help for 'help' command."""
        print(
            '\nhelp:\n'
            '    List available commands with "help" or detailed help '
            'with "help cmd".\n'
        )

    @staticmethod
    def help_info():
        """Output help for 'info' command."""
        print(
            '\ninfo <alias>:\n'
            '    Display details for a contact. Add "|" as a second '
            'argument to page the output.\n'
        )

    @staticmethod
    def help_list():
        """Output help for 'list' command."""
        print(
            '\nlist (ls) [alias|view]:\n'
            '    List a summary of all contacts except those tagged as '
            '\'archive\' (by default). Optionally, list a specific alias '
            'or use one of the views \'all\' (for all contacts including '
            'those tagged \'archive\') or \'favorite\' (for all contacts '
            'tagged \'favorite\'). Add \'|\' as an additional argument '
            'to page the output.\n\n'
            '    The following shortcuts are available:\n\n'
            '      lsa : list all\n'
            '      lsf : list favorite\n'
        )

    @staticmethod
    def help_modify():
        """Output help for 'modify' command."""
        print(
            '\nmodify <alias>:\n'
            '    Modify a contact file.\n'
        )

    @staticmethod
    def help_new():
        """Output help for 'new' command."""
        print(
            '\nnew:\n'
            '    Create a new contact file.\n'
        )

    @staticmethod
    def help_notes():
        """Output help for 'notes' command."""
        print(
            '\nnotes <alias>:\n'
            '    Edit the notes on a contact with $EDITOR. This is safer '
            'than editing the task directly with \'edit\', as it will '
            'ensure proper indentation for multi-line notes.\n'
        )

    @staticmethod
    def help_refresh():
        """Output help for 'refresh' command."""
        print(
            '\nrefresh:\n'
            '    Refresh the contact information from files on disk. '
            'This is useful if changes were made to files outside of '
            'the program shell (e.g. sync\'d from another computer).\n'
        )

    @staticmethod
    def help_search():
        """Output help for 'search' command."""
        print(
            '\nsearch <term>:\n'
            '    Search for contacts. May be in the form of '
            '[type]:[string] where type is one of: alias, name, email, '
            'phone, or tag. Queries without a type will search all of '
            'the aforementioned fields. Add "|" as a second argument '
            'to page the output.\n'
        )


class ModShell(Cmd):
    """Subshell for modifying a task.

    Attributes:
        contacts (obj): an instance of Contacts().
        uid (str):      the uid of the task being modified.
        alias (str):    the alias of the task being modified.

    """
    def __init__(
            self,
            contacts,
            uid,
            alias,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes a ModShell() object."""
        super().__init__()
        self.contacts = contacts
        self.uid = uid
        self.alias = alias

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )
        self.valid_attrs = [
            'email',
            'phone',
            'address',
            'messaging',
            'website',
            'pgpkey'
        ]

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args.startswith("del") or args.startswith("rm"):
            newargs = args.split()
            if len(newargs) > 1:
                newargs.pop(0)
                newargs = ' '.join(newargs)
                self.do_delete(newargs)
            else:
                self.do_delete("")
        elif args.startswith("quit") or args.startswith("exit"):
            return True
        else:
            print("\nNo such command. See 'help'.\n")

    @staticmethod
    def emptyline():
        """Ignore empty line entry."""

    @staticmethod
    def _error_pass(errormsg):
        """Print an error message but don't exit.

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')

    def _get_aliases(self):
        """Generates a list of all contact aliases.

        Returns:
            aliases (list): the list of all contact aliases.

        """
        aliases = []
        for contact in self.contacts.contacts:
            alias = self.contacts.contacts[contact].get('alias')
            if alias:
                aliases.append(alias.lower())
        return aliases

    def _set_prompt(self):
        """Set the prompt string."""
        if self.contacts.color_bold:
            self.prompt = f"\033[1mmodify ({self.alias})\033[0m> "
        else:
            self.prompt = f"modify ({self.alias})> "

    def do_add(self, args):
        """Add an email address, phone number, address, messaging
        account, website, or PGP key to a contact.

        Args:
            args (str): the command arguments.

        """
        commands = args.split()
        if len(commands) < 1:
            self.help_add()
        else:
            attr = str(commands[0]).lower()
            if attr not in self.valid_attrs:
                self.help_add()
            if attr == 'email':
                try:
                    self.contacts.add_new_email(another=False)
                except KeyboardInterrupt:
                    print("\nCancelled.")
                self.contacts.modify(
                    alias=self.alias,
                    add_email=self.contacts.add_emails)
                self.contacts.add_emails = None
            elif attr == 'phone':
                try:
                    self.contacts.add_new_phone(another=False)
                except KeyboardInterrupt:
                    print("\nCancelled.")
                self.contacts.modify(
                    alias=self.alias,
                    add_phone=self.contacts.add_phones)
                self.contacts.add_phones = None
            elif attr == 'address':
                try:
                    self.contacts.add_new_address(another=False)
                except KeyboardInterrupt:
                    print("\nCancelled.")
                self.contacts.modify(
                    alias=self.alias,
                    add_address=self.contacts.add_addresses)
                self.contacts.add_addresses = None
            elif attr == 'messaging':
                try:
                    self.contacts.add_new_messaging(another=False)
                except KeyboardInterrupt:
                    print("\nCancelled.")
                self.contacts.modify(
                    alias=self.alias,
                    add_messaging=self.contacts.add_messaging)
                self.contacts.add_messaging = None
            elif attr == 'website':
                try:
                    self.contacts.add_new_website(another=False)
                except KeyboardInterrupt:
                    print("\nCancelled.")
                self.contacts.modify(
                    alias=self.alias,
                    add_website=self.contacts.add_websites)
                self.contacts.add_websites = None
            elif attr == 'pgpkey':
                try:
                    self.contacts.add_new_pgpkey(another=False)
                except KeyboardInterrupt:
                    print("\nCancelled.")
                self.contacts.modify(
                    alias=self.alias,
                    add_pgpkey=self.contacts.add_pgpkeys)
                self.contacts.add_pgpkeys = None

    def do_alias(self, args):
        """Change the alias of a contact.

        Args:
            args (str): the command arguments.

        """
        commands = args.split()
        if len(commands) > 0:
            aliases = self._get_aliases()
            newalias = str(commands[0]).lower()
            if newalias in aliases:
                self._error_pass(
                        f"alias '{newalias}' already in use")
            else:
                self.contacts.modify(
                    alias=self.alias,
                    new_alias=newalias)
                self.alias = newalias
                self._set_prompt()
        else:
            self.help_alias()

    def do_anniversary(self, args):
        """Change the anniversary for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            anniversary = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_anniversary=anniversary)
        else:
            self.help_anniversary()

    def do_assistant(self, args):
        """Change the business assistant for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            assistant = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_assistant=assistant)
        else:
            self.help_assistant()

    def do_birthday(self, args):
        """Change the birthday for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            birthday = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_birthday=birthday)
        else:
            self.help_birthday()

    def do_calendar(self, args):
        """Change the calendar URL for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            calendar = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_calurl=calendar)
        else:
            self.help_calendar()

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_company(self, args):
        """Change the company name for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            company = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_company=company)
        else:
            self.help_company()

    def do_delete(self, args):
        """Delete an email address, phone number, address, messaging
        account, website, or PGP key from a contact.

        Args:
            args (str): the command arguments.

        """
        commands = args.split()
        if len(commands) < 2:
            self.help_delete()
        else:
            attr = str(commands[0]).lower()
            index = commands[1]
            if attr not in self.valid_attrs:
                self.help_delete()
            email_addr = [index] if attr == 'email' else None
            phone = [index] if attr == 'phone' else None
            address = [index] if attr == 'address' else None
            messaging = [index] if attr == 'messaging' else None
            website = [index] if attr == 'website' else None
            pgpkey = [index] if attr == 'pgpkey' else None

            self.contacts.modify(
                alias=self.alias,
                del_email=email_addr,
                del_phone=phone,
                del_address=address,
                del_messaging=messaging,
                del_website=website,
                del_pgpkey=pgpkey)

    def do_display(self, args):
        """Change the display name for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            display = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_display=display)
        else:
            self.help_display()

    def do_division(self, args):
        """Change the business division for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            division = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_division=division)
        else:
            self.help_division()

    @staticmethod
    def do_done(args):
        """Exit the modify subshell.

        Args:
            args (str): the command arguments, ignored.

        """
        return True

    def do_first(self, args):
        """Change the first name for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            first = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_first=first)
        else:
            self.help_first()

    def do_freebusy(self, args):
        """Change the freebusy URL for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            freebusy = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_fburl=freebusy)
        else:
            self.help_freebusy()

    def do_gender(self, args):
        """Change the gender for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            gender = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_gender=gender)
        else:
            self.help_gender()

    def do_info(self, args):
        """Display full details for the selected contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if str(commands[0]) == "|":
                self.contacts.info(self.alias, True)
            else:
                self.contacts.info(self.alias)
        else:
            self.contacts.info(self.alias)

    def do_language(self, args):
        """Change the preferred language for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            language = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_language=language)
        else:
            self.help_language()

    def do_last(self, args):
        """Change the last name for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            last = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_last=last)
        else:
            self.help_last()

    def do_manager(self, args):
        """Change the business manager for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            manager = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_manager=manager)
        else:
            self.help_manager()

    def do_nickname(self, args):
        """Change the nickname for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            nickname = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_nickname=nickname)
        else:
            self.help_nickname()

    def do_notes(self, args):
        """Edit contact notes via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        self.contacts.notes(self.alias)

    def do_office(self, args):
        """Change the business office for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            office = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_office=office)
        else:
            self.help_office()

    def do_photo(self, args):
        """Change the photo URL for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            photo = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_photo=photo)
        else:
            self.help_photo()

    def do_spouse(self, args):
        """Change the spouse name for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            spouse = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_spouse=spouse)
        else:
            self.help_spouse()

    def do_tags(self, args):
        """Change the tags for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            tags = str(commands[0])
            self.contacts.modify(
                alias=self.alias,
                new_tags=tags)
        else:
            self.help_tags()

    def do_title(self, args):
        """Change the business title for the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            title = str(args)
            self.contacts.modify(
                alias=self.alias,
                new_title=title)
        else:
            self.help_title()

    def do_unset(self, args):
        """Clear a field on the contact.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if len(commands) > 2:
                self.help_unset()
            else:
                field = str(commands[0]).lower()
                if field == 'calendar':
                    field = 'calurl'
                elif field == 'freebusy':
                    field = 'fburl'
                allowed_fields = [
                    'tags',
                    'first',
                    'last',
                    'nickname',
                    'birthday',
                    'anniversary',
                    'spouse',
                    'language',
                    'gender',
                    'company',
                    'title',
                    'division',
                    'manager',
                    'assistant',
                    'office',
                    'photo',
                    'calurl',
                    'fburl'
                ]
                if field in allowed_fields:
                    self.contacts.unset(self.alias, field)
                else:
                    self.help_unset()
        else:
            self.help_unset()

    @staticmethod
    def help_add():
        """Output help for 'add' command."""
        print(
            '\nadd <attr>:\n'
            '    Add an attribute to a contact record for one of the '
            'following: email, phone, address, messaging, website, '
            'pgpkey.\n'
        )

    @staticmethod
    def help_alias():
        """Output help for 'alias' command."""
        print(
            '\nalias <new alias>:\n'
            '    Change the alias of the contact.\n'
        )

    @staticmethod
    def help_anniversary():
        """Output help for 'anniversary' command."""
        print(
            '\nanniversary <YYYY-MM-DD>:\n'
            '    Change the anniversary of the contact.\n'
        )

    @staticmethod
    def help_assistant():
        """Output help for 'assistant' command."""
        print(
            '\nassistant <name>:\n'
            '    Change the business assistant of the contact.\n'
        )

    @staticmethod
    def help_birthday():
        """Output help for 'birthday' command."""
        print(
            '\nbirthday <YYYY-MM-DD>:\n'
            '    Change the birthday of the contact.\n'
        )

    @staticmethod
    def help_calendar():
        """Output help for 'calendar' command."""
        print(
            '\ncalendar <url>:\n'
            '    Change the calendar URL of the contact.\n'
        )

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_company():
        """Output help for 'company' command."""
        print(
            '\ncompany <name>:\n'
            '    Change the company of the contact.\n'
        )

    @staticmethod
    def help_delete():
        """Output help for 'delete' command."""
        print(
            '\ndelete (del, rm) <attr> <number>:\n'
            '    Delete an attribute from a contact record for one of '
            'the following: email, phone, address, messaging, website, '
            'pgpkey. The attribute to delete is identified by the index '
            'number for the attribute (next to the label).\n'
        )

    @staticmethod
    def help_display():
        """Output help for 'display' command."""
        print(
            '\ndisplay <display name>:\n'
            '    Change the display name of the contact.\n'
        )

    @staticmethod
    def help_division():
        """Output help for 'division' command."""
        print(
            '\ndivision <name>:\n'
            '    Change the business division of the contact.\n'
        )

    @staticmethod
    def help_done():
        """Output help for 'done' command."""
        print(
            '\ndone:\n'
            '    Finish modifying the contact.\n'
        )

    @staticmethod
    def help_first():
        """Output help for 'first' command."""
        print(
            '\nfirst <first name>:\n'
            '    Change the first name of the contact.\n'
        )

    @staticmethod
    def help_freebusy():
        """Output help for 'freebusy' command."""
        print(
            '\nfreebusy <url>:\n'
            '    Change the free/busy URL of the contact.\n'
        )

    @staticmethod
    def help_gender():
        """Output help for 'gender' command."""
        print(
            '\ngender <M/F/O/N/U;description>:\n'
            '    Change the gender of the contact.\n'
        )

    @staticmethod
    def help_info():
        """Output help for 'info' command."""
        print(
            '\ninfo [|]:\n'
            '    Display details for a contact. Add "|" as an'
            'argument to page the output.\n'
        )

    @staticmethod
    def help_language():
        """Output help for 'language' command."""
        print(
            '\nlanguage <language>:\n'
            '    Change the preferred language of the contact.\n'
        )

    @staticmethod
    def help_last():
        """Output help for 'last' command."""
        print(
            '\nlast <last name>:\n'
            '    Change the last name of the contact.\n'
        )

    @staticmethod
    def help_manager():
        """Output help for 'manager' command."""
        print(
            '\nmanager <name>:\n'
            '    Change the business manager of the contact.\n'
        )

    @staticmethod
    def help_nickname():
        """Output help for 'nickname' command."""
        print(
            '\nnickname <nickname>:\n'
            '    Change the nickname of the contact.\n'
        )

    @staticmethod
    def help_notes():
        """Output help for 'notes' command."""
        print(
            '\nnotes:\n'
            '    Edit the notes on a task with $EDITOR. This is safer '
            'than editing the task directly with \'edit\', as it will '
            'ensure proper indentation for multi-line notes.\n'
        )

    @staticmethod
    def help_office():
        """Output help for 'office' command."""
        print(
            '\noffice <name/location>:\n'
            '    Change the business office name or location of the '
            'contact.\n'
        )

    @staticmethod
    def help_photo():
        """Output help for 'photo' command."""
        print(
            '\nphoto <url>:\n'
            '    Change the photo URL of the contact.\n'
        )

    @staticmethod
    def help_spouse():
        """Output help for 'spouse' command."""
        print(
            '\nspouse <name>:\n'
            '    Change the spouse of the contact.\n'
        )

    @staticmethod
    def help_tags():
        """Output help for 'tags' command."""
        print(
            '\ntags <tag>[,tag]:\n'
            '    Modify the tags on the task. A comma-delimted list or '
            'you may use the + and ~ notations to add or delete a tag '
            'from the existing tags.\n'
        )

    @staticmethod
    def help_title():
        """Output help for 'title' command."""
        print(
            '\ntitle <title>:\n'
            '    Change the business title of the contact.\n'
        )

    @staticmethod
    def help_unset():
        """Output help for 'unset' command."""
        print(
            '\nunset <alias> <field>:\n'
            '    Clear a specified field of the contact. The field may '
            'be one of the following: tags, first, last, nickname, '
            'birthday, anniversary, spouse, language, gender, company, '
            'title, division, manager, assistant, office, photo, '
            'calendar, or freebusy.\n'
        )


def parse_args():
    """Parse command line arguments.

    Returns:
        args (dict):    the command line arguments provided.

    """
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description='Terminal-based address book for nerds.')
    parser._positionals.title = 'commands'
    parser.set_defaults(command=None)
    subparsers = parser.add_subparsers(
        metavar=f'(for more help: {APP_NAME} <command> -h)')
    pager = subparsers.add_parser('pager', add_help=False)
    pager.add_argument(
        '-p',
        '--page',
        dest='page',
        action='store_true',
        help="page output")
    addemail = subparsers.add_parser(
        'add-email')
    addemail.add_argument(
        'filename')
    addemail.set_defaults(command='addemail')
    config = subparsers.add_parser(
        'config',
        help='edit configuration file')
    config.set_defaults(command='config')
    delete = subparsers.add_parser(
        'delete',
        aliases=['rm'],
        help='delete contact')
    delete.add_argument(
        'alias',
        help="contact to delete")
    delete.add_argument(
        '-f',
        '--force',
        dest='force',
        action='store_true',
        help="delete without confirmation")
    delete.set_defaults(command='delete')
    edit = subparsers.add_parser(
        'edit',
        help='edit a contact file (uses $EDITOR)')
    edit.add_argument(
        'alias',
        help='contact alias')
    edit.set_defaults(command='edit')
    export = subparsers.add_parser(
        'export',
        help='search and output in vCard 4.0 format')
    export.add_argument(
        'term',
        help='search term')
    export.set_defaults(command='export')
    info = subparsers.add_parser(
        'info',
        parents=[pager],
        help='show details about a contact')
    info.add_argument(
        'alias',
        help='contact alias')
    info.set_defaults(command='info')
    listcmd = subparsers.add_parser(
        'list',
        parents=[pager],
        aliases=['ls'],
        help='list contacts')
    listcmd.add_argument(
        'view',
        nargs='?',
        default='normal',
        metavar='<view>',
        help='<none>, <alias>, \'all\', or \'favorite\'')
    listcmd.set_defaults(command='list')
    lsa = subparsers.add_parser('lsa', parents=[pager])
    lsa.set_defaults(command='lsa')
    lsf = subparsers.add_parser('lsf', parents=[pager])
    lsf.set_defaults(command='lsf')
    modify = subparsers.add_parser(
        'modify',
        aliases=['mod'],
        help='modify a contact')
    modify.add_argument(
        'alias',
        metavar='<alias>',
        help='contact alias to modify')
    modify.add_argument(
        '--anniversary',
        metavar='<date>',
        dest='new_anniversary',
        help='anniversary (YYYY-MM-DD)')
    modify.add_argument(
        '--assistant',
        metavar='<name>',
        dest='new_assistant',
        help='assistant name')
    modify.add_argument(
        '--birthday',
        metavar='<date>',
        dest='new_birthday',
        help='birthday (YYYY-MM-DD)')
    modify.add_argument(
        '--calurl',
        metavar='<url>',
        dest='new_calurl',
        help='calendar URL')
    modify.add_argument(
        '--company',
        metavar='<name>',
        dest='new_company',
        help='company name')
    modify.add_argument(
        '--display',
        metavar='<display name>',
        dest='new_display',
        help='the display name of the contact')
    modify.add_argument(
        '--division',
        metavar='<name>',
        dest='new_division',
        help='company division')
    modify.add_argument(
        '--fburl',
        metavar='<url>',
        dest='new_fburl',
        help='free/busy URL')
    modify.add_argument(
        '--first',
        metavar='<name>',
        dest='new_first',
        help='first name')
    modify.add_argument(
        '--gender',
        metavar='<abbr>[;description]',
        dest='new_gender',
        help='gender (M/F/O/N/U)')
    modify.add_argument(
        '--language',
        metavar='<language>',
        dest='new_language',
        help='preferred language')
    modify.add_argument(
        '--last',
        metavar='<name>',
        dest='new_last',
        help='last name')
    modify.add_argument(
        '--manager',
        metavar='<name>',
        dest='new_manager',
        help='manager name')
    modify.add_argument(
        '--new-alias',
        metavar='<alias>',
        dest='new_alias',
        help='a new alias for the contact')
    modify.add_argument(
        '--nickname',
        metavar='<name>',
        dest='new_nickname',
        help='nickname')
    modify.add_argument(
        '--notes',
        dest='new_notes',
        metavar='<text>',
        help='notes about the contact')
    modify.add_argument(
        '--office',
        metavar='<location>',
        dest='new_office',
        help='office location')
    modify.add_argument(
        '--photo',
        metavar='<url>',
        dest='new_photo',
        help='photo URL')
    modify.add_argument(
        '--spouse',
        metavar='<name>',
        dest='new_spouse',
        help='spouse name')
    modify.add_argument(
        '--tags',
        metavar='<tag>[,tag]',
        dest='new_tags',
        help='tag(s)')
    modify.add_argument(
        '--title',
        metavar='<description>',
        dest='new_title',
        help='business title')
    modify.add_argument(
        '--add-address',
        metavar=('<label> <address>', 'primary'),
        nargs='+',
        dest='add_address',
        action='append',
        help=(
            'add address '
            '(format: address1;address2;city;state;zipcode;country)'))
    modify.add_argument(
        '--add-email',
        metavar=('<label> <address>', 'primary'),
        nargs='+',
        dest='add_email',
        action='append',
        help='add email address')
    modify.add_argument(
        '--add-messaging',
        metavar=('<label> <account>', 'primary'),
        nargs='+',
        dest='add_messaging',
        action='append',
        help='add messaging account')
    modify.add_argument(
        '--add-pgpkey',
        metavar=('<label> <url>', 'primary'),
        nargs='+',
        dest='add_pgpkey',
        action='append',
        help='add PGP key URL')
    modify.add_argument(
        '--add-phone',
        metavar=('<label> <number>', 'primary'),
        nargs='+',
        dest='add_phone',
        action='append',
        help='add phone number')
    modify.add_argument(
        '--add-website',
        metavar=('<label> <url>', 'primary'),
        nargs='+',
        dest='add_website',
        action='append',
        help='add website address')
    modify.add_argument(
        '--del-address',
        metavar='<index>',
        dest='del_address',
        action='append',
        help='delete address')
    modify.add_argument(
        '--del-email',
        metavar='<index>',
        dest='del_email',
        action='append',
        help='delete email address')
    modify.add_argument(
        '--del-messaging',
        metavar='<index>',
        dest='del_messaging',
        action='append',
        help='delete messaging address')
    modify.add_argument(
        '--del-pgpkey',
        metavar='<index>',
        dest='del_pgpkey',
        action='append',
        help='delete PGP key URL')
    modify.add_argument(
        '--del-phone',
        metavar='<index>',
        dest='del_phone',
        action='append',
        help='delete phone number')
    modify.add_argument(
        '--del-website',
        metavar='<index>',
        dest='del_website',
        action='append',
        help='delete website address')
    modify.set_defaults(command='modify')
    mutt = subparsers.add_parser(
        'mutt',
        help='output for mutt query')
    mutt.add_argument(
        'term',
        help='query to find contact')
    mutt.set_defaults(command='mutt')
    new = subparsers.add_parser(
        'new',
        help='create a new contact')
    new.add_argument(
        '--address',
        metavar=('<label> <address>', 'primary'),
        nargs='+',
        action='append',
        help=(
            'address '
            '(format: address1;address2;city;state;zipcode;country)'
        ))
    new.add_argument(
        '--alias',
        metavar='<alias>',
        help='a custom alias for the contact')
    new.add_argument(
        '--anniversary',
        metavar='<date>',
        help='anniversary (YYYY-MM-DD)')
    new.add_argument(
        '--assistant',
        metavar='<name>',
        help='assistant name')
    new.add_argument(
        '--birthday',
        metavar='<date>',
        help='birthday (YYYY-MM-DD)')
    new.add_argument(
        '--calurl',
        metavar='<url>',
        help='calendar URL')
    new.add_argument(
        '--company',
        metavar='<name>',
        help='company name')
    new.add_argument(
        '--display',
        metavar='<display name>',
        help='the display name of the contact')
    new.add_argument(
        '--division',
        metavar='<name>',
        help='company division')
    new.add_argument(
        '--email',
        metavar=('<label> <address>', 'primary'),
        nargs='+',
        action='append',
        help='email address')
    new.add_argument(
        '--fburl',
        metavar='<url>',
        help='free/busy URL')
    new.add_argument(
        '--first',
        metavar='<name>',
        help='first name')
    new.add_argument(
        '--gender',
        metavar='<abbr>[;description]',
        help='gender (M/F/O/N/U)')
    new.add_argument(
        '--language',
        metavar='<language>',
        help='preferred language')
    new.add_argument(
        '--last',
        metavar='<name>',
        help='last name')
    new.add_argument(
        '--manager',
        metavar='<name>',
        help='manager name')
    new.add_argument(
        '--messaging',
        metavar=('<label> <account>', 'primary'),
        nargs='+',
        action='append',
        help='messaging account')
    new.add_argument(
        '--nickname',
        metavar='<name>',
        help='nickname')
    new.add_argument(
        '--notes',
        metavar='<text>',
        help='notes about the contact')
    new.add_argument(
        '--office',
        metavar='<location>',
        help='office location')
    new.add_argument(
        '--pgpkey',
        metavar=('<label> <url>', 'primary'),
        nargs='+',
        action='append',
        help='PGP key URL')
    new.add_argument(
        '--phone',
        metavar=('<label> <number>', 'primary'),
        nargs='+',
        action='append',
        help='phone number')
    new.add_argument(
        '--photo',
        metavar='<url>',
        help='photo URL')
    new.add_argument(
        '--spouse',
        metavar='<name>',
        help='spouse name')
    new.add_argument(
        '--tags',
        metavar='<tag>[,tag]',
        help='tag(s)')
    new.add_argument(
        '--title',
        metavar='<description>',
        help='business title')
    new.add_argument(
        '--website',
        metavar=('<label> <url>', 'primary'),
        nargs='+',
        action='append',
        help='website address')
    new.set_defaults(command='new')
    notes = subparsers.add_parser(
        'notes',
        help='add/update notes on a contact (uses $EDITOR)')
    notes.add_argument(
        'alias',
        help='contact alias')
    notes.set_defaults(command='notes')
    query = subparsers.add_parser(
        'query',
        help='search contacts with structured text output')
    query.add_argument(
        'term',
        help='search term')
    query.add_argument(
        '-l',
        '--limit',
        dest='limit',
        help='limit output to specific field(s)')
    query.add_argument(
        '-j',
        '--json',
        dest='json',
        action='store_true',
        help='output as JSON rather than TSV')
    query.set_defaults(command='query')
    search = subparsers.add_parser(
        'search',
        parents=[pager],
        help='search contacts')
    search.add_argument(
        'term',
        help='search term')
    search.set_defaults(command='search')
    shell = subparsers.add_parser(
        'shell',
        help='interactive shell')
    shell.set_defaults(command='shell')
    unset = subparsers.add_parser(
        'unset',
        help='clear a field from a specified contact')
    unset.add_argument(
        'alias',
        help='contact alias')
    unset.add_argument(
        'field',
        help='field to clear')
    unset.set_defaults(command='unset')
    version = subparsers.add_parser(
        'version',
        help='show version info')
    version.set_defaults(command='version')
    parser.add_argument(
        '-c',
        '--config',
        dest='config',
        metavar='<file>',
        help='config file')
    args = parser.parse_args()
    return parser, args


def main():
    """Entry point. Parses arguments, creates Contacts() object, calls
    requested method and parameters.

    """
    if os.environ.get("XDG_CONFIG_HOME"):
        config_file = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_CONFIG_HOME"])), APP_NAME, "config")
    else:
        config_file = os.path.expandvars(
            os.path.expanduser(DEFAULT_CONFIG_FILE))

    if os.environ.get("XDG_DATA_HOME"):
        data_dir = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_DATA_HOME"])), APP_NAME)
    else:
        data_dir = os.path.expandvars(
            os.path.expanduser(DEFAULT_DATA_DIR))

    parser, args = parse_args()

    if args.config:
        config_file = os.path.expandvars(
            os.path.expanduser(args.config))

    contacts = Contacts(
        config_file,
        data_dir,
        DEFAULT_CONFIG)

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)
    elif args.command == "addemail":
        contacts.add_from_mutt(args.filename)
    elif args.command == "config":
        contacts.edit_config()
    elif args.command == "mutt":
        contacts.mutt(args.term)
    elif args.command == "modify":
        contacts.modify(
            alias=args.alias,
            new_alias=args.new_alias,
            new_display=args.new_display,
            new_tags=args.new_tags,
            new_first=args.new_first,
            new_last=args.new_last,
            new_nickname=args.new_nickname,
            new_birthday=args.new_birthday,
            new_anniversary=args.new_anniversary,
            new_spouse=args.new_spouse,
            new_language=args.new_language,
            new_gender=args.new_gender,
            new_company=args.new_company,
            new_title=args.new_title,
            new_division=args.new_division,
            new_manager=args.new_manager,
            new_assistant=args.new_assistant,
            new_office=args.new_office,
            new_photo=args.new_photo,
            new_calurl=args.new_calurl,
            new_fburl=args.new_fburl,
            new_notes=args.new_notes,
            add_email=args.add_email,
            del_email=args.del_email,
            add_phone=args.add_phone,
            del_phone=args.del_phone,
            add_address=args.add_address,
            del_address=args.del_address,
            add_messaging=args.add_messaging,
            del_messaging=args.del_messaging,
            add_website=args.add_website,
            del_website=args.del_website,
            add_pgpkey=args.add_pgpkey,
            del_pgpkey=args.del_pgpkey)
    elif args.command == "new":
        contacts.new(
            alias=args.alias,
            display=args.display,
            tags=args.tags,
            first=args.first,
            last=args.last,
            nickname=args.nickname,
            birthday=args.birthday,
            anniversary=args.anniversary,
            spouse=args.spouse,
            language=args.language,
            gender=args.gender,
            company=args.company,
            title=args.title,
            division=args.division,
            manager=args.manager,
            assistant=args.assistant,
            office=args.office,
            photo=args.photo,
            calurl=args.calurl,
            fburl=args.fburl,
            notes=args.notes,
            emails=args.email,
            phones=args.phone,
            addresses=args.address,
            messaging=args.messaging,
            websites=args.website,
            pgpkeys=args.pgpkey)
    elif args.command == "lsa":
        contacts.list("all", args.page)
    elif args.command == "lsf":
        contacts.list("favorite", args.page)
    elif args.command == "list":
        contacts.list(args.view, args.page)
    elif args.command == "info":
        contacts.info(args.alias, args.page)
    elif args.command == "delete":
        contacts.delete(args.alias, args.force)
    elif args.command == "edit":
        contacts.edit(args.alias)
    elif args.command == "notes":
        contacts.notes(args.alias)
    elif args.command == "search":
        contacts.search(args.term, args.page)
    elif args.command == "query":
        contacts.query(args.term, limit=args.limit, json_output=args.json)
    elif args.command == "export":
        contacts.export(args.term)
    elif args.command == "unset":
        contacts.unset(args.alias, args.field)
    elif args.command == "shell":
        contacts.interactive = True
        shell = ContactsShell(contacts)
        shell.cmdloop()
    elif args.command == "version":
        print(f"{APP_NAME} {APP_VERS}")
        print(APP_COPYRIGHT)
        print(APP_LICENSE)
    else:
        sys.exit(1)


# entry point
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
