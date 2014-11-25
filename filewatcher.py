"""
Filewatcher.

Notifies about modifications in files in a specified directory tree.
Outputs summary upon which the user is supposed to take an action if
files were locally modified - to update them on the server himself.
Catches situation when a file or files were modified, were added or
disappeared from a watched directory tree.

Internal data is stored in a JSON file (contains list of files, their
last modification time). This database file can be stored in an arbitrary
location or in the root of the watched directory tree

Developed for the Merel.cz company, Plzen, Czech Republic


Usage, command line arguments, configuration file values:
    filewatcher.py [init|check] options
        options:
            -c, --config config-file-path
            -d, --directory watched-directory-tree
            -b, --database internal-data-file-path
            -h, --help prints out usage message

author: Zdenek Maxa


TODO:
-GUI window listing files watched over
-with GUI, automatic database file update can be instructed
-pyxmaxlibs proper dependency integration (pyxmaxlibs needs to be deployable)
-do logging as log ... yet configurable format ... (no self ...)
-do via CSV (with header) database format

"""


import json
import logging
import os
import sys
import time
from ConfigParser import RawConfigParser
from optparse import OptionParser, TitledHelpFormatter

from pyxmaxlibs import helpers
from pyxmaxlibs.logger import Logger


DATABASE_FILE = "filewatcher-db.json"
CONFIGURATION_FILE = "filewatcher.conf"
LOG_LEVEL = logging.DEBUG


def process_config_file(config, logger):
    """
    Processes applications configuration file.
    Config file entries are added to (previously non-existent attributes
        in the input config instance which has been built based upon 
        command line input arguments.
    All configuration items from the config file are stored in lists.

    """
    # if the config file was not specified, just set default config values
    if not os.path.exists(config.config_file):
        setattr(config, "watch_masks", [])
        setattr(config, "ignore_list", [])
        logger.info("Specified config file '%s' does not exist, using "
                    "default values." % config.config_file)
        return config
    logger.info("Processing config file '%s' ..." % config.config_file)
    # Raw - doesn't do any interpolation
    parser = RawConfigParser()
    # by default it seems that value names are converted to lower case,
    # this way they should be case-sensitive
    parser.optionxform = str
    # does not fail even on a non-existing file
    parser.read(config.config_file)
    try:
        for (name, value) in parser.items("general"):
            # assumes that ',' is the separator of configuration values
            values = value.split(',')
            # trimm white spaces
            val_trimmed = [val.strip() for val in values]
            # entry will always be a list
            setattr(config, name, val_trimmed)
    except (ValueError, IndexError) as ex:
        msg = "Error while processing configuration file, reason: %s" % ex
        helpers.print_msg_exit(msg=msg, exit_code=1)
    return config


def process_cli_args(cli_args, logger):
    """
    Process options and arguments provided on the command line
    and transform into configuration settings.

    """
    form = TitledHelpFormatter(width=78)
    usage = "%prog init|check [options]"
    parser = OptionParser(usage=usage, formatter=form)
    # option, its value
    parser.add_option("-c",
                      "--config",
                      dest="config_file",
                      default="",
                      help="Path to the configuration file. If not "
                           "specified, current directory is probed if "
                           "file '%s' exists there." % CONFIGURATION_FILE)
    parser.add_option("-d",
                      "--directory",
                      dest="watched_dir",
                      default="",
                      help="Absolute path to the watched directory. "
                           "Files in the the directory will be analyzed "
                           "when 'check' or internal database file "
                           "(re)created on 'init'.")
    parser.add_option("-b",
                      "--database",
                      dest="database",
                      default="",
                      help="Path to the internal database file which is "
                           "created on 'init' or loaded on 'check'. "
                           "Running 'init' without -b specified stores "
                           "the databse file in the -d location. This "
                           "option is mandatory for 'check' action.")
    opts, args = parser.parse_args(cli_args)
    # first argument is application's name, second option should be action
    if len(args) != 2 or args[1] not in ("init", "check"):
        msg = ("None, wrong or more than allowed arguments specified, "
               "try --help")
        helpers.print_msg_exit(msg=msg, exit_code=1)
    else:
        opts.action = args[1]
    # process options
    if not opts.config_file:
        cur_dir = os.getcwd()
        logger.info("Option --config not specified, trying to load "
                    "'%s' from the directory '%s' ..." %
                    (CONFIGURATION_FILE, cur_dir))
        config_file = os.path.join(cur_dir, CONFIGURATION_FILE)
        if os.path.exists(config_file):
            opts.config_file = config_file
            logger.info("File '%s' exists." % opts.config_file)
        else:
            logger.info("No configuration file will be loaded.")
    if not opts.watched_dir:
        opts.watched_dir = os.getcwd()
        logger.info("Option --directory not specified, working in '%s'." %
                    opts.watched_dir)
    if not opts.database:
        opts.database = os.path.join(opts.watched_dir, DATABASE_FILE)
        logger.info("Option --database not specified, using '%s'." %
                    opts.database)
    return opts


class FileWatcher(object):
    """
    FileWatcher class performing init and check actions and summarizing
    report to the user.
    Takes configuration values in the config instance.

    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self._modified = []
        self._removed = []
        self._added = []


    def init(self):
        """
        List all files in the watched directory conforming the file masks,
        excluding files in the ignore list and generate internal database
        file listing all those files and their last modification timestamp.

        """
        self.logger.info("Performing initialization ...")
        self.logger.info("Processing '%s' directory ..." %
                          self.config.watched_dir)
        db_file = self.config.database
        if os.path.exists(db_file):
            os.rename(db_file, db_file + ".backup." + str(time.time()))
            self.logger.warn("Database file '%s' exists, backupped." %
                             db_file)
        # returns full file paths
        file_names = helpers.get_files(path=self.config.watched_dir,
                                       file_mask=self.config.watch_masks,
                                       recursive=True)
        # result data dictionary (dictonary of dictionaries):
        #   file_path: {last_modif: <value>, last_modif_human: <value>}
        data = {}
        for name in file_names:
            if name in self.config.ignore_list:
                continue
            dt = os.path.getmtime(name)
            human = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(dt))
            data[name] = dict(last_modif=dt, last_modif_human=human)
        # store resulting data into JSON file
        self.logger.info("Storing timestamp info about %s files ..." %
                len(data))
        f = open("tempfiledata.txt", 'w')

        TODO TODO TODO ...

        f.write(str(data))
        f.close()
        try:
            db_file_fp = open(db_file, 'w')
            json.dump(data, db_file_fp)
            db_file_fp.close()
            self.logger.info("Finished, database file written: '%s'" %
                             db_file)
        except IOError, ex:
            self.logger.error("Could not write data into '%s', reason: %s'" %
                              (db_file, ex))


    def check(self):
        """
        Check all files in the supplied database file.
        If modification data disagrees, files are listed in the summary.
        Newly added files and removed files are detected and reported.

        """
        self.logger.info("Performing check ... (database file: '%s')" %
                         self.config.database)
        # read the database file
        try:
            f = open(self.config.database)
            data = json.load(f)
            f.close()
        except Exception, ex:
            self.logger.error("Could not read database file, reason: %s" % ex)
            return 1
        # perform actual check against the database file
        # data: {file_path: {last_modif: <value>, last_modif_human: <value>}}
        for file_name, values in data.items():
            try:
                dt = os.path.getmtime(file_name)
                if dt != values["last_modif"]:
                    self._modified.append(file_name)
            except OSError:
                self._removed.append(file_name)
        # check actual files in the directory tree - check for newly
        # added files
        # get files currently in the directory - returns full file paths
        curr_file_names = helpers.get_files(path=self.config.watched_dir,
                                            file_mask=self.config.watch_masks,
                                            recursive=True)
        for file_name in curr_file_names:
            if file_name in self.config.ignore_list:
                continue
            if file_name not in data.keys():
                self._added.append(file_name)
        self.summarize()


    def summarize(self):
        def printer(title, whats):
            print title
            for what in whats:
                print "    %s" % what
            print "\n"

        print "\n", 80 * '='
        print "Summary:\n"
        printer("Removed:", self._removed)
        printer("New:", self._added)
        printer("Modified:", self._modified)


def main():
    logger = Logger(name="filewatcher", level=LOG_LEVEL)
    logger.info("Processing command line arguments ...")
    config = process_cli_args(sys.argv, logger)
    config = process_config_file(config, logger)
    logger.debug("Configuration values:\n%s" % config)
    watcher = FileWatcher(config, logger)
    ret_val = getattr(watcher, config.action)()
    logger.info("Finished.")
    if ret_val:
        sys.exit(ret_val)


if __name__ == "__main__":
    main()
