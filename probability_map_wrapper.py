#! /usr/bin/env python3

"""
Probability map and label maker wrapper
Greg Conan: conan@ohsu.edu
Created 2020-06-09
Updated 2021-09-14
"""

##################################
#
# Wrapper for probability map labeler Bash scripts
#
##################################

# Standard Python imports
import argparse
from datetime import datetime
import difflib
import math
import numpy as np
import os
import shutil
import socket
import subprocess
import sys

# Get path to this script's parent directory
CODE_DIR_FLAG = "--code-dir"
if CODE_DIR_FLAG in sys.argv:
    PWD = sys.argv[sys.argv.index(CODE_DIR_FLAG) + 1]
else:
    PWD = os.path.dirname(os.path.abspath(__file__))
os.chdir(PWD)

# Constants: Paths to this script's directory (PWD) and to Bash scripts)
SCRIPT_MAKE_MAPS = os.path.join(PWD, "make_maps.sh")
SCRIPT_LABEL_MAP = os.path.join(PWD, "label_map.sh")

# Constants: Default paths, numeric parameters, and hex values for color file
DEFAULT_COLORFILE = "colorfile.csv"
DEFAULT_FILENAME = "combined_clusters"
MIDTHICKNESS_PATH = ("/mnt/rose/shared/projects/ABCD/average_surfaces/data/"
                     "{}.midthickness.surf.gii")
DEFAULT_OUTPUT = os.path.join(PWD,
                              datetime.now().strftime("%Y-%m-%d_%H-%M"))
DEFAULT_MIN_AREA = 200
DEFAULT_OVERLAP_LO_THRESH = 0.75
DEFAULT_PROB_DIR = os.path.join(PWD, "GRP1_singlenet_copy", "")
DEFAULT_STEP = 0.05
DEFAULT_UP_THRESH = 1.0
COLORS = {"Aud": "255,0,255,255",
          "CO": "128,0,128,255",
          "DAN": "0,110,255,255",
          "DMN": "255,0,0,255",
          "FP": "0,192,0,255",
          "MTL": "192,160,0,255",
          "PMN": "192,192,192,255",
          "PON": "0,255,255,255",
          "Sal": "0,0,0,255",
          "SMd": "0,0,0,255",
          "SMl": "255,0,128,255",
          "Tpole": "128,0,128,255",
          "VAN": "0,0,128,255",
          "Vis": "0,0,255,255"}
 
def main():
    cli_args = _cli()
    setattr(cli_args, "colorfile", os.path.abspath(cli_args.colorfile))

    # Go to output folder (for relative paths in label_map.sh) and run scripts
    os.chdir(cli_args.output)
    if not os.path.exists(cli_args.colorfile):
        color_fmt = get_colorfile_format(cli_args)

    # List every threshold
    print(math.log10(cli_args.upper_threshold))
    digits = max(count_digits_of(x) for x in (
        cli_args.upper_threshold, cli_args.low_threshold, cli_args.step
    )) + 1
    all_thresholds = [round(x, digits) for x in np.arange(
        cli_args.upper_threshold, cli_args.low_threshold,
        round(0 - abs(cli_args.step), digits)
    )]
    
    # Create a label for every threshold
    for each_thresh in all_thresholds:
        out_dir = os.path.join(cli_args.output,
                               "thresh{}".format(each_thresh), "")
        os.makedirs(out_dir, exist_ok=True)
        os.chdir(out_dir)

        # Make maps at each threshold unless user said to skip this step
        if not cli_args.skip_map_maker:
            run_make_maps(cli_args, each_thresh, out_dir)
            for each_file in os.scandir(out_dir):
                os.chmod(each_file.path, 0o775)

        # Only run label map script if above the lower threshold of overlap
        if each_thresh >= cli_args.low_threshold:
            # copy_if_not_exists(PWD, "{}.txt".format(cli_args.filename), out_dir)
            # copy_if_not_exists(PWD, "combined_parcel.csv", out_dir)
            if os.path.exists(cli_args.colorfile):
                colorfile = copy_color_file(cli_args, out_dir)
            else:
                make_color_file(cli_args, out_dir, color_fmt, each_thresh)
                colorfile = cli_args.colorfile
            try:
                run_label_map(cli_args, out_dir, colorfile)
            except subprocess.CalledProcessError:
                pass


def _cli():
    """
    Get and validate all arguments from command line using argparse.
    :return: argparse.Namespace with all validated inputted command line args
    """
    parser = argparse.ArgumentParser()
    MSG_DEFAULT = "By default, if this flag is excluded, its value will be {}. "
    MSG_VAL_WHOLE_NUM = "This argument must be a positive integer. "
    MSG_MIDTHIC = "Valid path to a real {} midthickness surface .gii file. "

    parser.add_argument(
        CODE_DIR_FLAG,
        type=valid_readable_dir,
        help=("Valid path to the existing directory containing this .py file. "
              "In other words, the top level of the repository. This flag is "
              "only needed if you are running this script as a SLURM job.")
        
    )

    parser.add_argument(
        "-color",
        "--colorfile",
        default=DEFAULT_COLORFILE,
        help=("Name of an existing .csv file mapping each probability "
              ".dscalar.nii file to its color in the output region labels. "
              "Colors must be given in RGBA format with values from 0 to 1. "
              + MSG_DEFAULT.format(DEFAULT_COLORFILE))
    )

    parser.add_argument(
        "-file",
        "--filename",
        default=DEFAULT_FILENAME,
        help=("Base name of the file containing a list of the label numbers "
              "and their RGBA values. This argument does not include the file "
              "extension. There should be a .txt file in the PWD with this "
              "base name. " + MSG_DEFAULT.format(DEFAULT_FILENAME))
    )

    parser.add_argument(
        "--increment",
        "-step",
        dest="step",
        default=DEFAULT_STEP,
        type=float,
        help=("Increment between thresholds at which to create label files. ")
    )

    parser.add_argument(
        "-left",
        "--left-midthickness",
        type=valid_readable_file,
        dest="left",
        default=MIDTHICKNESS_PATH.format("L"),
        help=(MSG_MIDTHIC.format("left")
              + MSG_DEFAULT.format(MIDTHICKNESS_PATH.format("L")))
    )

    parser.add_argument(
        "-right",
        "--right-midthickness",
        type=valid_readable_file,
        dest="right",
        default=MIDTHICKNESS_PATH.format("R"),
        help=(MSG_MIDTHIC.format("right")
              + MSG_DEFAULT.format(MIDTHICKNESS_PATH.format("R")))
    )

    parser.add_argument(
        "-low", "-lo",
        "--low-threshold",
        type=float, 
        default=DEFAULT_OVERLAP_LO_THRESH,
        help="Lower threshold at which to stop making .dlabel.nii files."
              
    )

    parser.add_argument(
        "-out",
        "--output",
        type=valid_output_dir,
        default=DEFAULT_OUTPUT,
        help=("Valid path to the folder where this script will save its "
              "output files. If the folder does not exist at the given path, "
              "then this script will make a new one. "
              + MSG_DEFAULT.format(DEFAULT_OUTPUT))
    )

    parser.add_argument(
        "-prob", "-prob-dir",
        "--probability-folder",
        type=valid_readable_dir,
        default=DEFAULT_PROB_DIR,
        help=("Valid path to an existing directory containing the probability "
              "map .dscalar.nii files which will be used to create the output "
              ".dlabel.nii files. " + MSG_DEFAULT.format(DEFAULT_PROB_DIR)),
    )
    
    parser.add_argument(
        "-skip",
        "--skip-map-maker",
        action="store_true",
        help=("Takes no parameters. Include this flag to skip making maps "
              "using make_maps.sh and instead only make .dlabel.nii files "
              "by running label_map.sh.")
    )

    parser.add_argument(
        "-surf", "-min-surf",
        "--min-surf-area",
        type=valid_whole_number,
        default=DEFAULT_MIN_AREA,
        help=("Minimum surface area. {}{}"
              .format(MSG_VAL_WHOLE_NUM, MSG_DEFAULT.format(DEFAULT_MIN_AREA)))
    )

    parser.add_argument(
        "-up", "--upper-threshold",
        type=float, 
        default=DEFAULT_UP_THRESH,
        help="Upper threshold at which to start making .dlabel.nii files."
    )

    parser.add_argument(
        "-vol", "-min-vol", "--min-vol-area",
        type=valid_whole_number,
        default=DEFAULT_MIN_AREA,
        help=("Minimum surface volume. {}{}"
              .format(MSG_VAL_WHOLE_NUM, MSG_DEFAULT.format(DEFAULT_MIN_AREA)))
    )

    parser.add_argument(
        "-wb",
        "--wb-command",
        default=get_default_wb_command(),
        help=("Path to wb_command file to run Workbench Command. If this flag "
              "is excluded, then the script will try to guess the path to "
              "the wb_command file by checking the user's BASH aliases and "
              "several default paths. Your default wb_command is '{}'. If "
              "that says 'None', then you need to include this argument."
              .format(get_default_wb_command()))
    )

    return parser.parse_args()


def validate(an_obj, is_real, make_valid, err_msg, prepare=None):
    """
    Parent/base function used by different type validation functions. Raises an
    argparse.ArgumentTypeError if the input is somehow invalid.
    :param an_obj: Object to check if it represents a valid result 
    :param is_real: Function which returns True only if an_obj is valid
    :param make_valid: Function which returns a fully validated an_obj
    :param err_msg: String to show to user to tell them what is invalid
    :param prepare: Function to prepare an_obj before validation
    :return: an_obj, but fully validated
    """
    try:
        if prepare:
            prepare(an_obj)
        assert is_real(an_obj)
        return make_valid(an_obj)
    except (OSError, TypeError, AssertionError, ValueError, 
            argparse.ArgumentTypeError):
        raise argparse.ArgumentTypeError(err_msg.format(an_obj))


def valid_whole_number(to_validate):
    """
    Throw argparse exception unless to_validate is an integer greater than 0
    :param to_validate: Object to test whether it is an integer greater than 0
    :return: to_validate if it is an integer greater than 0
    """
    return validate(to_validate, lambda x: int(to_validate) > 0, int, 
                    "{} is not a positive integer.")


def valid_readable_file(path):
    """
    Throw exception unless parameter is a valid readable filename string. This
    is used instead of argparse.FileType("r") because the latter leaves an open
    file handle, which has caused problems.
    :param path: Parameter to check if it represents a valid filename
    :return: String representing a valid filename
    """
    return validate(path, lambda x: os.access(x, os.R_OK),
                    os.path.abspath, "Cannot read file at {}")


def valid_readable_dir(path):
    """
    :param path: Parameter to check if it represents a valid directory path
    :return: String representing a valid directory path
    """
    return validate(path, os.path.isdir, valid_readable_file,
                    "{} is not a valid readable directory path")
    

def valid_output_dir(path):
    """
    Try to create a directory to write files into at the given path, and throw 
    argparse exception if that fails
    :param path: String which is a valid (not necessarily real) folder path
    :return: String which is a validated absolute path to real writeable folder
    """
    return validate(path, lambda x: os.path.isdir(x) and os.access(x, os.W_OK),
                    valid_readable_file, "Cannot create directory at {}", 
                    lambda y: os.makedirs(y, exist_ok=True))


def get_default_wb_command():
    """
    Try to get valid path to default wb_command file
    :return: String, path to wb_command if on Exacloud or on Rushmore
             or the user has 'wb_command' alias in their .bashrc / $PATH
    """
    # If wb_command is already in BASH PATH, then use it
    try:
        subprocess.check_call(("which", "wb_command"))
        wb_command = "wb_command"
    except subprocess.CalledProcessError:

        # Otherwise, get a default path based on the server
        hostname = socket.gethostname().lower()
        if "exa" in hostname:
            wb_command = ("/home/exacloud/lustre1/fnl_lab/code/external/utilities/"
                          "workbench-1.3.2/bin_rh_linux64/wb_command")
        elif hostname == "rushmore":
            wb_command = "/mnt/max/software/workbench/bin_linux64/wb_command"
        else:
            wb_command = None

    return wb_command


def count_digits_of(a_num):
    """
    :param a_num: Numeric value
    :return: Integer which is the number of digits in a_num
    """
    return 1 if a_num == 0 else abs(int(math.log10(a_num)))


def copy_if_not_exists(orig_dir, filename, new_dir):
    """
    Copy a file with a specific name from one folder into another unless there
    is already a file with that name in the destination directory.
    :param orig_dir: String with the path to a directory to copy a file out of
    :param filename: String naming the file in orig_dir to copy to new_dir
    :param new_dir: String with the path to a directory to copy the file into
    """
    orig_path = os.path.join(orig_dir, filename)
    new_path = os.path.join(new_dir, filename)
    if not os.access(os.path.join(new_dir, filename), os.R_OK):
        print("copying {} from {} to {}".format(filename, orig_dir, new_dir))
        shutil.copy2(orig_path, new_path)
    

def get_colorfile_format(cli_args):
    """
    Assuming that all filenames in the probability folder are in the same
    format, such that the only difference between their names is which brain
    region/network they are, get the parts of their filenames which are shared
    :param cli_args: argparse.Namespace with all command-line arguments
    :return: String which is the basename of all filenames in the probability
             folder, except replacing the differences between them with '{}'
    """
    prob_files = os.scandir(cli_args.probability_folder)
    file1 = next(prob_files).name
    file2 = next(prob_files).name
    matcher = difflib.SequenceMatcher(None, file1, file2)
    blocks = matcher.get_matching_blocks()
    string = '{}'.join([file1[a:a+n] for a, _, n in blocks])
    if string[-2:] == "{}":
        string = string[:-2]
    return string


def make_color_file(cli_args, out, color_fmt, thresh):
    """
    :param cli_args: argparse.Namespace with all command-line arguments
    :param out: String with a valid path to the output directory
    :param color_fmt: String with the basename of all files in the probability
                      folder, except with their differences replaced by '{}'
    :return: N/A
    """
    path = os.path.join(out, cli_args.colorfile)
    to_write = []

    # Make a list of lines to write mapping each color to a probability file
    for shortname in COLORS.keys():
        prob_file = os.path.join(cli_args.probability_folder,
                                 color_fmt.format(shortname))
        if not os.access(prob_file, os.R_OK):
            sys.exit("Error: Probability file not found at {}"
                     .format(prob_file))
        
        new_fname = split_2_exts(color_fmt.format(shortname))
        to_write.append(",".join((new_fname[0] + "_at_{}".format(thresh)
                                  + new_fname[1], # os.path.join(out,
                                  shortname, COLORS[shortname])))
        
        # to_write.append(",".join((prob_file, shortname, COLORS[shortname])))

    # Write list of lines to the color file 
    with open(path, "w+") as colorfile:
        colorfile.write("\n".join(to_write))


def copy_color_file(cli_args, out):
    """
    Copy the contents of the --colorfile into a new file, keeping the file
    names (but not the directory paths) from each path in the --colorfile
    :param cli_args: argparse.Namespace with all command-line arguments
    :param out: String with a valid path to the output directory
    :return: String with a valid path to the newly created color file
    """
    to_write = []
    new_color_file = os.path.join(out, os.path.basename(cli_args.colorfile))
    with open(cli_args.colorfile, "r") as infile:
        for each_line in infile:
            to_write.append(each_line.split(","))
            to_write[-1][0] = os.path.basename(to_write[-1][0])
            to_write[-1] = ",".join(to_write[-1])    
    with open(new_color_file, "w+") as outfile:
        outfile.write("\n".join(to_write))
    return new_color_file


def split_2_exts(filepath):
    """
    :param filepath: String that's a valid path to a file with 2 extensions,
                     e.g. /home/file1.dscalar.nii
    :return: Tuple of 2 elements, where the 2nd is the 2 extensions and the
             1st is everything else, e.g. ('/home/file1', '.dscalar.nii')
    """
    base_plus_ext1, ext2 = os.path.splitext(filepath)
    basename, ext1 = os.path.splitext(base_plus_ext1)
    return basename, ext1 + ext2


def print_and_run(msg, cmd):
    """
    :param msg: String to print to tell the user that the command will now run
    :param cmd: List of strings, which is a command to run
    """
    print("Running {}".format(msg), "\n", cmd)
    subprocess.check_call(cmd)


def run_make_maps(cli_args, threshold, out_dir):
    """
    :param cli_args: argparse.Namespace with all command-line arguments
    :param out_dir: String with a valid path to the output directory
    """
    print_and_run("{} at threshold {}".format(SCRIPT_MAKE_MAPS, threshold),
                  (SCRIPT_MAKE_MAPS, str(threshold),
                   cli_args.probability_folder,
                   out_dir, out_dir, cli_args.wb_command,
                   str(cli_args.min_surf_area),
                   str(cli_args.min_vol_area),
                   cli_args.left, cli_args.right))


def run_label_map(cli_args, out_dir, colorfile):
    """
    :param cli_args: argparse.Namespace with all command-line arguments
    :param out_dir: String with a valid path to the output directory
    """
    print_and_run(SCRIPT_LABEL_MAP, (SCRIPT_LABEL_MAP, cli_args.filename,
                                     out_dir, colorfile, cli_args.wb_command))


if __name__ == "__main__":
    main()
