from flask import current_app, g, render_template, json
from flask.cli import with_appcontext
from datetime import date
from . import db, env_label
from .models import StoredSpecial, Status, ParserStatus
from .criteria import important_only, important_special
from .parsers import PARSERS
import app.message as message
import click, os, traceback


@click.command(help="Reset all specials' error attributes to false & overall health to true.")
@with_appcontext
def reset_errors():
    for special in StoredSpecial.query:
        special.error = False
    set_health(True)
    db.session.commit()

@click.command(help="Store contents of website data from parser NAME to use with local_specials.")
@click.argument('name')
@click.option('-e', '--extension', default='html', help=("The extension you would like to use for "
                                                         "the file that will be created. The "
                                                         "default is 'html'."))
@with_appcontext
def store_specials_data(name, extension):
    for Parser in PARSERS:
        dvc_parser = Parser()
        if dvc_parser.source == name:
            mode = 'wb'
            specials_data = dvc_parser.get_specials_page()
            if (isinstance(specials_data, str) or
                isinstance(specials_data, list) or
                isinstance(specials_data, dict)):
                mode = 'w'
            elif not isinstance(specials_data, bytes):
                print(f'Unable to write parser data to file (Type: {type(specials_data)})')

            with open(f'{dvc_parser.source}.{extension}', mode) as f:
                if isinstance(specials_data, bytes) or isinstance(specials_data, str):
                    f.write(specials_data)
                else:
                    json.dump(specials_data, f)
            print(f"'{dvc_parser.source}' data has been stored!")
            return
    print(f"No parser with the name '{name}' was found.")

@click.command(name="update-specials", help='Update all DVC specials & send messages when changes are found.')
@click.option('--local', 'local_specials', multiple=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True),
                         envvar="LOCAL_SPECIALS",
                         help=('Load specials from the given files. The files must be named the name of '
                               'the parser they are being used for.'))
@click.option('--email/--no-email', 'send_email', default=True,
                         help='Specifies whether an email should be sent if changes to the current specials are found.')
@click.option('--error-report', 'send_error_report', is_flag=True,
                         help='Produce an error report via email of all of the current errors.')
@with_appcontext
def update_specials_cli(local_specials, send_email, send_error_report):
    update_specials(local_specials, send_email, send_error_report)

def update_specials(local_specials, send_email, send_error_report):
    g.send_error_report = send_error_report
    try:
        #Get the current specials from either the Internet or a local file
        all_current_specials = get_current_specials(local_specials)
        all_new_specials = {}
        all_stored_specials = []
        all_updated_specials_tuple = []
        all_removed_specials_list = []

        for parser_source in all_current_specials:
            #Make a copy of all the specials, needed for when we check everything
            #for errors later
            new_specials = all_current_specials[parser_source].copy()

            if len(new_specials) == 0:
                if not empty_parser_error(parser_source):
                    continue

            # Since the parser has specials in it, set it to healthy
            parser_healthy(parser_source)

            #Get the stored specials from the db
            stored_specials = StoredSpecial.query.filter_by(source=parser_source).order_by(StoredSpecial.check_in, StoredSpecial.check_out).all()

            #Check for any changes to the specials
            updated_specials_tuple, removed_specials_list = check_for_changes(new_specials, stored_specials)

            all_new_specials.update(new_specials)
            all_stored_specials.extend(stored_specials)
            all_updated_specials_tuple.extend(updated_specials_tuple)
            all_removed_specials_list.extend(removed_specials_list)

        #Adding new Specials
        new_specials_list, new_important_specials = store_new_specials(all_new_specials, all_stored_specials)

        #Updating Old Specials
        updated_specials_list, updated_important_specials = update_old_specials(all_updated_specials_tuple)

        #Deleting Removed Specials
        removed_specials_list = remove_old_specials(all_removed_specials_list)

        #Send an email if we need to.... i.e. if there were any kind of updates
        changes = []
        if len(new_specials_list) > 0:
            changes.append(('Added', new_specials_list))
        if len(updated_specials_list) > 0:
            changes.append(('Updated', updated_specials_list))
        if len(removed_specials_list) > 0:
            changes.append(('Removed', removed_specials_list))
        if changes and send_email:
            email_message = render_template('email_template.html',
                                            specials_group=changes,
                                            env_label=env_label.get(current_app.env))
            message.send_update_email(email_message)

            #Send a text if any of the changes were considered important
            if new_important_specials or updated_important_specials:
                message.send_update_text_message()
        elif changes and not send_email:
            print("Changes found, not sending email. Bada-bing, bada-BOOM!")
        else:
            print("No changes found. Nothing to update Cap'n. :-)")

        #Handle any errors that were generated during the parsing of the specials
        handle_errors(all_current_specials, all_stored_specials)
        set_health(True)
    except Exception as e:
        unhandled_error(e)

    db.session.commit()

def get_current_specials(local_specials):
    all_new_specials = {}
    for Parser in PARSERS:
        dvc_parser = Parser()
        local_special = local_special_for_parser(dvc_parser, local_specials)
        dvc_parser_specials = dvc_parser.get_all_specials(local_special)

        #Probably want to move this check into 'update_specials'. Putting it there
        #will allow for an error to be tracked but won't require an exception to
        #be thrown. As an idea, I could make the following changes to implement
        #this:
        #   1) Rather than returning a dictionary with specials and their id's as
        #      keys, I could add each parsers dict into a dict with the parser
        #      name as the key.
        #   2) In 'update_specials' check if any specific parser is empty.
        #   3) If a parser is empty create a list with the bad (and also maybe
        #      the good) parsers.
        #   4) Use the good list to filter the database query with and use the
        #      bad list in the error message

        # if len(dvc_parser_specials) == 0:
        #     msg = f"There is a problem getting data from the '{dvc_parser.source}' website."
        #     print(msg)
        #     raise Exception(msg)
        all_new_specials[dvc_parser.source] = dvc_parser_specials
    return all_new_specials

def store_new_specials(new_specials, stored_specials):
    send_important_only = important_only()
    new_important_specials = False
    new_specials_list = []
    for new_special_key in new_specials:
        special_entry = add_special(new_specials[new_special_key])
        stored_specials.append(special_entry)
        important = important_special(special_entry)
        if not (not important and send_important_only): #The only time it isn't added is when the special is not important and we only want to send important specials
            new_specials_list.append(special_entry)
        new_important_specials = new_important_specials or important

    if len(new_specials_list) > 1:
        new_specials_list = sorted(new_specials_list, key=lambda special: (special.check_in if special.check_in else date(2000,1,1),
                                                                           special.check_out if special.check_out else date(2000,1,1)))

    return new_specials_list, new_important_specials

def update_old_specials(updated_specials_tuple):
    send_important_only = important_only()
    updated_important_specials = False
    updated_specials_list = []
    for special_tuple in updated_specials_tuple:
        parsed_special, stored_special = special_tuple
        stored_special.update_with_special(parsed_special)
        important = important_special(stored_special)
        if not (not important and send_important_only):
            updated_specials_list.append(stored_special)
        updated_important_specials = updated_important_specials or important

    return updated_specials_list, updated_important_specials

def remove_old_specials(removed_specials):
    send_important_only = important_only()
    removed_specials_list = []
    for stored_special in removed_specials:
        remove_special(stored_special)
        important = important_special(stored_special)
        if not (not important and send_important_only):
            removed_specials_list.append(stored_special)

    return removed_specials_list

def check_for_changes(new_specials, stored_specials):
    updated_specials_tuple = []
    removed_specials_list = []
    for stored_special in stored_specials:
        if stored_special.special_id in new_specials:
            new_special = new_specials[stored_special.special_id]
            if stored_special != new_special:
                updated_specials_tuple.append((new_special, stored_special))
            del new_specials[stored_special.special_id]
        else:
            removed_specials_list.append(stored_special)

    return updated_specials_tuple, removed_specials_list

def add_special(parsed_special):
    special_entry = StoredSpecial.from_parsed_special(parsed_special)
    db.session.add(special_entry)
    return special_entry

def remove_special(stored_special):
    db.session.delete(stored_special)

def handle_errors(new_specials, stored_specials):
    new_specials_flat = {}
    for key in new_specials:
        new_specials_flat.update(new_specials[key])
    new_specials_errors = [new_specials_flat[stored_special.special_id] for stored_special in stored_specials if stored_special.new_error]
    if len(new_specials_errors) > 0:
        error_msg = render_template('error_template.html', specials=new_specials_errors,
                                    env_label=env_label.get(current_app.env))
        print('Uhh-ohh, Houston, we have a problem. There appears to be an error.')
        message.send_error_email(error_msg)
        message.send_error_text_messsage()

    if g.send_error_report:
        all_specials_errors = [new_specials_flat[stored_special.special_id] for stored_special in stored_specials if stored_special.error]
        all_empty_parsers = ParserStatus.query.filter_by(healthy=False).all()
        if len(all_specials_errors) > 0 or len(all_empty_parsers) > 0:
            error_msg = render_template('error_template.html', specials=all_specials_errors,
                                        empty_parsers=all_empty_parsers,
                                        env_label=env_label.get(current_app.env), error_report=True)
            print('So, about that bug...when are you going to catch it? Producing Error Report.')
            message.send_error_report_email(error_msg)

def empty_parser_error(parser_source):
    parser_status = get_parser_status(parser_source)
    if parser_status.healthy and not parser_status.empty_okay:
        parser_status.healthy = False
        print('Umm hello?...Anyone Home?')
        error_msg = render_template('empty_parser_template.html', parser_source=parser_source,
                                    env_label=env_label.get(current_app.env))
        message.send_error_email(error_msg)
        message.send_error_text_messsage()
    elif not parser_status.healthy and parser_status.empty_okay:
        parser_status.healthy = True
    return parser_status.empty_okay

def parser_healthy(parser_source):
    parser_status = get_parser_status(parser_source)
    parser_status.healthy = True

def get_parser_status(parser_source):
    parser_status = ParserStatus.query.filter_by(parser_source=parser_source).first()
    if parser_status is None:
        parser_status = ParserStatus(parser_source=parser_source,
                                     healthy=True)
        db.session.add(parser_status)
    return parser_status


def unhandled_error(error):
    traceback.print_exc()
    db.session.rollback()
    healthy = check_health()
    if healthy or g.send_error_report:
        error_msg = f'Unhandled Exception: {error_type(error)}\n\n{error}\n\n{traceback.format_exc()}'
        send_error_func = message.send_error_report_email if g.send_error_report else message.send_error_email
        send_error_func(error_msg, html_message=False)
        if healthy:
            message.send_error_text_messsage()
        set_health(False)

# From traceback.py in CPython Line #563
def error_type(error):
    err_type = type(error).__qualname__
    err_mod = type(error).__module__
    if err_mod not in ("__main__", "builtins"):
        err_type = err_mod + '.' + err_type
    return err_type

def get_status():
    status = Status.query.first()
    if not status:
        status = Status(healthy=True)
        db.session.add(status)
    return status

def check_health():
    return get_status().healthy

def set_health(healthy):
    status = get_status()
    if status.healthy != healthy:
        status.healthy = healthy

def local_special_for_parser(parser, local_specials):
    for local_special in local_specials:
        if parser.source == os.path.splitext(os.path.basename(local_special))[0]:
            return local_special
