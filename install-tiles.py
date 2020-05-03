# install_tiles.py
# NCSSAR mbtiles installer

# since caltopo/sartopo cannot read nested directories more than one level deep
#  (confirmed by Matt Jacobs 4-20-20) we need to copy nested files from the source
#  to the appropriate top level directory on the target
# (the reason for the nesting in the first place is to define nested subsets
#  of map layer sets for various device types / available storage space)

# SYNTAX:
#   python install_tiles.py <root> <directory_set> [<target>]
#
#    <directory_set> must either be the name of a text file in the current directory,
#      or the name of a subdirectory at some level under <root>;
#      if a text file (this is tried first): the file must contain one filename
#       per line, in which case those files are copied from <root> to <target> 
#      if a directory name: all files recursively from that level and down will
#       be copied to the target directory: if the file is a caltopo-named mbtiles
#       file, it will be copied to the same-named subdirectory of root as the leaf
#       directory name of the source; otherwise it will be copied to the target directory
#    target = name of the target directory; if omitted, no copy will be done,
#      but instead, a list of target filenames will be written to <directory_set>.txt
#      as if the target directory were the current directory 
#


import os
import sys
import shutil
import re
from pathlib import Path

[root,dirset]=sys.argv[1:3]

target=None
if len(sys.argv)>3:
    target=sys.argv[3]
else:
    fnlist=[]

# if dirset is a text file, do all the work in this loop, then exit
copylist=None
if os.path.isfile(dirset):
    if not target:
        print("ERROR: target must be specified when using a text file as the copy list.")
        exit()
    copylist=[line.rstrip('\n') for line in open(dirset)]
#     print("Copy list:\n"+str(copylist))
    print("Installing from specified copy list...")
    for c in copylist:
        leaf=os.path.split(c)[0]
        fulltargetdir=os.path.join(target,leaf)
        os.makedirs(fulltargetdir,exist_ok=True)
        c=os.path.join(root,c)
        if os.path.isfile(c):
            print(c+" --> "+fulltargetdir)
            shutil.copy(c,fulltargetdir)
        else:
            print("SKIPPING non-existent file "+c+" specified in the list file")
    print("\nDone.")
    exit()

if not os.path.isdir(root):
    print("ERROR: Specified root directory "+str(root)+" was not found.")
    exit()

if target:
    os.makedirs(target,exist_ok=True)


# 1. find root dir with same name as first argument
basedir=None
for tup in os.walk(root):
    if tup[0].endswith(dirset):
        basedir=tup[0]
if basedir:
    print("Base directory found: "+basedir)
else:
    print("ERROR: Specified directory set "+dirset+" was not found under the current directory.")
    exit()
    
# 2. start flat-copying from that root dir
#  - if a given mbtiles file follows the caltopo naming convention,
#      copy it to <target>/<leafdir_of_file_in_question>
#    - otherwise, copy to <target>
for tup in os.walk(basedir):
    [dir,subdirs,files]=tup
    leafdirname=os.path.split(dir)[1]
    for fn in files:
        s=os.path.join(dir,fn)
        if re.search(".*-\d+-\d+-\d\d.mbtiles",fn):
            if target:
                td=os.path.join(target,leafdirname)
                os.makedirs(td,exist_ok=True)
                print(s+" --> "+td)
                shutil.copy(s,os.path.join(td,fn))
            else:
                fnlist.append(os.path.join(leafdirname,fn))
        else:
            if target:
                print("NON-CALTOPO file: "+s+" --> "+target)
                shutil.copy(os.path.join(dir,fn),os.path.join(target,fn))
            else:
                fnlist.append(fn)

if not target:
    fnfile=open(dirset+".txt","w")
    for fn in fnlist:
        fnfile.write(fn+"\n")
    fnfile.close()

print("\nDone.")
