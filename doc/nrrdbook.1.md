---
title: NRRDBOOK
section: 1
header: User Manual
footer: nrrdbook 0.0.2
date: January 3, 2022
---
# NAME
nrrdbook - Terminal-based address book for nerds.

# SYNOPSIS
**nrrdbook** *command* [*OPTION*]...

# DESCRIPTION
**nrrdbook** is a terminal-based address book program with advanced search options, formatted output, mutt/neomutt integration, and contact data stored in local text files. It can be run in either of two modes: command-line or interactive shell.

# OPTIONS
**-h**, **--help**
: Display help information.

**-c**, **--config** *file*
: Use a non-default configuration file.

# COMMANDS
**nrrdbook** provides the following commands and options.

**add-email** *filename*
: Add a contact by parsing the From: line of an email. This command is intended for mutt integration use only and is hidden from help and auto-completion.

**config**
: Edit the **nrrdbook** configuration file.

**delete (rm)** *alias* [*OPTION*]
: Delete a contact and contact file. The user will be prompted for confirmation.

    *OPTIONS*

    **-f**, **--force**
    : Force deletion, do not prompt for confirmation.
       
 
**edit** *alias*
: Edit a contact file in the user's editor (defined by the $EDITOR environment variable). If $EDITOR is not defined, an error message will report that.

**export** *searchterm*
: Search and output results in vCard 4.0 format, to STDOUT.

**info** *alias* [*OPTION*]
: Show the full details about a contact record.

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.


**list (ls)** [*view*] [*OPTION*]...
: Disply contacts in a formatted tabular list. An optional *view* argument can be provided to filter the list output. The *normal* view is default, and will list all contacts not tagged 'archive'. The *favorite* view will list all contacts tagged 'favorite'. A specific contact can be listed by providing the contact's alias as the view name.

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.


**modify (mod)** *alias* [*OPTION*]...
: Modify a contact.

    *OPTIONS*

    **--anniversary** *YYYY-MM-DD*
    : The contact's anniversary (e.g., wedding anniversary, hire date, etc).

    **--assistant** *name*
    : The contact's assistant or direct report.

    **--birthday** *YYYY-MM-DD*
    : The contact's birthday.

    **--calurl** *URL*
    : A URL representing the contact's calendar.

    **--company** *name*
    : The contact's company name.

    **--display** *name*
    : The contact's display name.

    **--division** *name*
    : The contact's corporate or institutional division.

    **--fburl** *URL*
    : A URL representing the contact's free/busy information.

    **--first** *name*
    : The contact's first (given) name.

    **--gender** *ABBR;description*
    : The contact's gender, in the form of a standard abbreviation optionally followed by descriptive text (separated by a semicolon [;]). The abbreviation may be one of: **M** (male), **F** (female), **O** (other), **N** (none or not applicable), or **U** (unknown).

    **--language** *language*
    : The contact's preferred language. For export compatibility vCard, use an ISO standard abbreviation (e.g., EN, FR, etc.)

    **--last** *name*
    : The contact's last (family) name.

    **--manager** *name*
    : The name of the contact's manager.

    **--new-alias** *alias*
    : A new custom alias to use for the contact. All aliases must be unique.

    **--nickname** *name*
    : The contact's nickname.

    **--notes** *text*
    : Notes to add to the contact. Be sure to properly escape the text if it includes special characters or newlines that may be interpretted by the shell. Using this option, any existing notes on the contact will be replaced. This command option is included mainly for the purpose of automated note insertion (i.e., via script or command). For more reliable note editing, use the **notes** command.

    **--office** *name*
    : The contact's office name or description.

    **--photo** *URL*
    : A URL representing the contact's photo.

    **--spouse** *name*
    : The name of the contact's spouse.

    **--tags** *tag[,tag]*
    : Tags assigned to the contact. This can be a single tag or multiple tags in a comma-delimited list. Normally with this option, any existing tags assigned to the contact will be replaced. However, this option also supports two special operators: **+** (add a tag to the existing tags) and **~** (remove a tag from the existing tags). For example, *--tags +documentation* will add the *documentation* tag to the existing tags on a contact, and *--tags ~testing,experimental* will remove both the *testing* and *experimental* tags from a contact.

    **--title** *description*
    : The contact's business or official title.

    **--add-address** *label* *address* [*primary*]
    : Add an address to a contact. Every address should have a unique label (e.g., 'work' or 'home') and may optionally be designated as the primary address. The address string itself must be provided in the following format: *address line 1*;*address line 2*;*city*;*state*;*zipcode*;*country*. Any blank fields must still be included and will look like *..;;..*.

    Examples:

        101 Main St;;Chicago;IL;60618;United States

        1134 W. 12th St;Apt 234;Austin;TX;78701;United States

        ;;Dexter;ME;

    **--add-email** *label* *address* [*primary*]
    : Add an email address to a contact. Every email address should have a unique label (e.g., 'work' or 'home') and may optionally be designated as the primary email address.

    **--add-messaging** *label* *account* [*primary*]
    : Add a messaging account address to a contact. Every messaging account should have a unique label (e.g., 'xmpp') and if exported to vCard the label will also be used as the protocol descriptor. A messaging account may optionally be designated as the primary messaging account.

    **--add-pgpkey** *label* *URL* [*primary*]
    : Add a PGP key URL to a contact. Every PGP key entry should have a unique label (e.g., 'personal' or 'business') and may optionally be designated as the primary PGP key for a contact.

    **--add-phone** *label* *number* [*primary*]
    : Add a phone number to a contact. Every phone number should have a unique label (e.g., 'work' or 'home') and may optionally be designated as the primary phone number.

    **--add-website** *label* *URL* [*primary*]
    : Add a website URL to a contact. Every website entry should have unique label (e.g., 'personal' or 'company') and may optionally be designated as the primary website.

    **--del-address** *index*
    : Delete an address from a contact. The address is identified by the index displayed in the output of **info**.

    **--del-email** *index*
    : Delete an email address from a contact. The email address is identified by the index displayed in the output of **info**.

    **--del-messaging** *index*
    : Delete a messaging account from a contact. The account is identified by the index displayed in the output of **info**.

    **--del-pgpkey** *index*
    : Delete a PGP key from a contact. The key is identified by the index displayed in the output of **info**.

    **--del-phone** *index*
    : Delete a phone number from a contact. The number is identified by the index displayed in the output of **info**.

    **--del-website** *index*
    : Delete a website from a contact. The website is identified by the index displayed in the output of **info**.


**mutt** *searchterm*
: Search for one or more contacts and output in a manner that can be parsed by mutt/neomutt.

**new** [*OPTION*]
: Create a new contact.

    *OPTIONS*

    **--address** *label* *address* [*primary*]
    : Add an address to a contact. Every address should have a unique label (e.g., 'work' or 'home') and may optionally be designated as the primary address. The address string itself must be provided in the following format: *address line 1*;*address line 2*;*city*;*state*;*zipcode*;*country*. Any blank fields must still be included and will look like *..;;..*. See **--add-address** under **modify** above for examples.

    **--alias** *alias*
    : A custom alias to use for the contact. All aliases must be unique.

    **--anniversary** *YYYY-MM-DD*
    : The contact's anniversary (e.g., wedding anniversary, hire date, etc).

    **--assistant** *name*
    : The contact's assistant or direct report.

    **--birthday** *YYYY-MM-DD*
    : The contact's birthday.

    **--calurl** *URL*
    : A URL representing the contact's calendar.

    **--company** *name*
    : The contact's company name.

    **--display** *name*
    : The contact's display name.

    **--division** *name*
    : The contact's corporate or institutional division.

    **--email** *label* *address* [*primary*]
    : Add an email address to a contact. Every email address should have a unique label (e.g., 'work' or 'home') and may optionally be designated as the primary email address.

    **--fburl** *URL*
    : A URL representing the contact's free/busy information.

    **--first** *name*
    : The contact's first (given) name.

    **--gender** *ABBR;description*
    : The contact's gender, in the form of a standard abbreviation optionally followed by descriptive text (separated by a semicolon [;]). The abbreviation may be one of: **M** (male), **F** (female), **O** (other), **N** (none or not applicable), or **U** (unknown).

    **--language** *language*
    : The contact's preferred language. For export compatibility vCard, use an ISO standard abbreviation (e.g., EN, FR, etc.)

    **--last** *name*
    : The contact's last (family) name.

    **--manager** *name*
    : The name of the contact's manager.

    **--messaging** *label* *account* [*primary*]
    : Add a messaging account address to a contact. Every messaging account should have a unique label (e.g., 'xmpp') and if exported to vCard the label will also be used as the protocol descriptor. A messaging account may optionally be designated as the primary messaging account.

    **--nickname** *name*
    : The contact's nickname.

    **--notes** *text*
    : Notes to add to the contact. Be sure to properly escape the text if it includes special characters or newlines that may be interpretted by the shell. Using this option, any existing notes on the contact will be replaced. This command option is included mainly for the purpose of automated note insertion (i.e., via script or command). For more reliable note editing, use the **notes** command.

    **--office** *name*
    : The contact's office name or description.

    **--pgpkey** *label* *URL* [*primary*]
    : Add a PGP key URL to a contact. Every PGP key entry should have a unique label (e.g., 'personal' or 'business') and may optionally be designated as the primary PGP key for a contact.

    **--phone** *label* *number* [*primary*]
    : Add a phone number to a contact. Every phone number should have a unique label (e.g., 'work' or 'home') and may optionally be designated as the primary phone number.

    **--photo** *URL*
    : A URL representing the contact's photo.

    **--spouse** *name*
    : The name of the contact's spouse.

    **--tags** *tag[,tag]*
    : Tags assigned to the contact. This can be a single tag or multiple tags in a comma-delimited list. Normally with this option, any existing tags assigned to the contact will be replaced. However, this option also supports two special operators: **+** (add a tag to the existing tags) and **~** (remove a tag from the existing tags). For example, *--tags +documentation* will add the *documentation* tag to the existing tags on a contact, and *--tags ~testing,experimental* will remove both the *testing* and *experimental* tags from a contact.

    **--title** *description*
    : The contact's business or official title.

    **--website** *label* *URL* [*primary*]
    : Add a website URL to a contact. Every website entry should have unique label (e.g., 'personal' or 'company') and may optionally be designated as the primary website.


**notes** *alias*
: Add or update notes on a contact using the user's editor (defined by the $EDITOR environment variable). If $EDITOR is not defined, an error message will report that.

**query** *searchterm* [*OPTION*]...
: Search for one or more contacts and produce plain text output (by default, tab-delimited text).

    *OPTIONS*

    **-l**, **--limit**
    : Limit the output to one or more specific fields (provided as a comma-delimited list).

    **-j**, **--json**
    : Output in JSON format rather than the default tab-delimited format.


**search** *searchterm* [*OPTION*]
: Search for one or more contacts output a tabular list (same format as **list**).

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.


**shell**
: Launch the **nrrdbook** interactive shell.

**unset** *alias* *field*
: Clear a field from a specified contact.

**version**
: Show the application version information.

# NOTES

## About primary entries
A physical or postal address, an email address, a phone number, a messaging account, a website, or a PGP key may be designated as *primary*. Primary entries are highlighted in **list** and **info** views using bold text (if enabled). Also, **query** output may be limited (using the **--limit** option) to only show email, phone number, and address results that are designated as *primary* (e.g., **--limit name,email:primary**).

## Changing the primary entry
If you wish to change the primary entry for emails, phone numbers, etc., you must delete the existing entries and re-add them with the primary keyword. For example, if the *[1] work* entry of a contact is primary and you would like to make *[2] home* the new primary:

    nrrdbook modify aw4d --del-email 1 --del-email 2 --add-email work tom@tomco.com --add-email home tom@homeisp.com primary

Alternatively, you may use the edit command to edit the contact file directly. Primary entries are designated via *primary: true*.

## Special tags
There are two special tags used by **nrrdbook**:

*archive* : contacts tagged with 'archive' will not appear in **list** output, unless the **-a**, **--all** option is included (command **listall** in interactive mode, shortcut **lsa**).

*favorite* : only contacts tagged with 'favorite' will be included in **list** if the **-f**, **--favorite** option is included (command **fav** in interactive mode, shortcut **lsf**).

## Search and query
There are two command-line methods for filtering the presented list of address book entries: **search** and **query**. These two similar-sounding functions perform very different roles.

Search results are output in the same tabular, human-readable format as that of list. Query results are presented in the form of tab-delimited text (by default) or JSON (if using the **-j**, **--json** option) and are primarily intended for use by other programs that are able to consume structured text output.

Search and query use the same filter syntax. The most basic form of search is to simply look for part of a name:

    nrrdbook search <search_term>

**NOTE:** search terms are case-insensitive.

If the search term is present in a contact's display name, the contact record will be displayed.

Optionally, a search type may be specified to search other fields. The search type may be one of *uid*, *alias*, *name*, *email*, *phone*, *address*, *birthday*, *anniversary*, or *tags*. If an invalid search type is provided, the search will default to a display name (*name*) search. To specify a search type, use the format:

    nrrdbook search [search_type=]<search_term>

You may combine search types in a comma-delimited structure. All search criteria must be met to return a result.

The tags search type may also use the optional **+** operator to search for more than one tag. Any matched tag will return a result.

The special search term *any* can be used to match all records, but is only useful in combination with an exclusion to match all records except those excluded.

## Exclusion
In addition to the search term, an exclusion term may be provided. Any match in the exclusion term will negate a match in the search term. An exclusion term is formatted in the same manner as the search term, must follow the search term, and must be denoted using the **%** operator:

    nrrdbook search [search_type=]<search_term>%[exclusion_type=]<exclusion_term>

## Search examples
Search for any entry with the word "john" in the display name:

    nrrdbook search john

The same search with the search type explicitly defined:

    nrrdbook search name=john

Search for all entries named "John" who live in Maine except for those tagged business or archive:

    nrrdbook search name=john,address=maine%tags=business+archive

## Birthdays and anniversaries
Searches for birthdays and anniversaries have special handling because of their particular use case.

    nrrdbook search birthday=09-23

The above search will find any entries with a birthday of September 23. The following search will return only those entries with the specific birthday of September 23, 1984.

    nrrdbook search birthday=1984-09-23

The following search will return any entries born any day in 1985:

    nrrdbook search birthday=1985

This search will return any entries for birthdays in October:

    nrrdbook search birthday=10

## Query and limit
The query function uses the same syntax as search but can return more information and will output in a form that may be read by other programs. The standard fields returned by query for tab-delimited output are:

    - uid (string)
    - alias (string)
    - display name (string)
    - email addresses (list)
    - phone numbers (list)
    - address entries (list)
    - birthday (string)
    - anniversary (string)
    - tags (list)

List fields are returned in standard Python format: ['item 1', 'item 2', ...]. Empty lists are returned as []. Empty string fields will appear as multiple tabs.

JSON output returns all fields for a record, including fields not provided in tab-delimited output.

The **query** function may also use the **--limit** option. This is a comma-separated list of fields to return. The **--limit** option does not have an effect on JSON output.

## Primary entries
Email addresses, phone numbers, and physical/mailing addresses may be tagged as *primary: true* denoting that this is the record's primary or preferred contact entry. To limit the **query** data returned to only the primary entry of a field, you may use one or more of the following limits:

    - email:primary
    - phone:primary
    - address:primary

For example, the following would search for any entry with a birthday in November which is not tagged as enemies and will limit the output to only name, birthday, and the person's primary email address:

    nrrdbook query birthday=11%tags=enemies --limit name,email:primary,birthday

Which would return output such as:

    Jan Morris  ['jan@somedomain.org']  1983-11-19
    Darun Singh ['dsingh@otherdomain.com']  1975-11-24

which might be useful in sending automated digital birthday cards by email. Another example might be generating a mailing list for holiday cards:

    nrrdbook query tags=holiday --limit name,address:primary

## Paging
Output from **list**, **search**, and **info** can get long and run past your terminal buffer. You may use the **-p** or **--page** option in conjunction with **search**, **list**, or **info** to page output.

## Mutt and Neomutt integration
**nrrdbook** may be used as an address book for **mutt** or **neomutt**. Add the following to your *muttrc* to support lookups using **nrrdbook**:

    set query_command = "nrrdbook mutt %s"

The **mutt** subcommand returns output in the standard mutt query form:

    email_address,display_name,alias

The query searches only the *alias*, *display*, and *email* fields for matches. If the query is an exact match for a record's alias, **nrrdbook** will return only a single entry with the primary email address (if designated by *primary: true*, otherwise the first email address defined). Non-exact matches return all email addresses found. For example:

    > nrrdbook mutt jrb1
    jack@brownindustries.com,Jack R. Brown,jrb1

    > nrrdbook mutt jack
    jack@brownindustries.com,Jack R. Brown,jrb1
    jack@homewebmail.com,Jack R. Brown,jrb1
    lisa@morrishendersonllc.com,Lisa Jackson,ljmh



# FILES
**~/.config/nrrdbook/config**
: Default configuration file

**~/.local/share/nrrdbook**
: Default data directory

# AUTHORS
Written by Sean O'Connell <https://sdoconnell.net>.

# BUGS
Submit bug reports at: <https://github.com/sdoconnell/nrrdbook/issues>

# SEE ALSO
Further documentation and sources at: <https://github.com/sdoconnell/nrrdbook>
