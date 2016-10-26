# coding: utf-8
#!/usr/bin/env python
from __future__ import print_function, absolute_import, division

import logging

from errno import EACCES
from os.path import realpath, basename
from sys import argv, exit
from threading import Lock
from datetime import datetime
import hashlib

import os
import sys

path = os.path.join(os.path.dirname(__file__), './lib')
sys.path.append(path)
sys.path.append(path + "/fusepy")

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

import db
from db import File, Source, Destination, CopyLog

class ReuseTrackFS(LoggingMixIn, Operations):
    def __init__(self, root):
        self.root = realpath(root)
        self.rwlock = Lock()

    def __call__(self, op, path, *args):
        return super(ReuseTrackFS, self).__call__(op, self.root + path, *args)

    def access(self, path, mode):
        if not os.access(path, mode):
            raise FuseOSError(EACCES)

    def chmod(self, path, mode):
        return os.chmod(path, mode)

    def chown(self, path, uid, gid):
        return os.chown(path, uid, gid)

    def create(self, path, mode):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        print_with_time("Create %s(%d)" % (path, inode(path)))
        return fd

    def flush(self, path, fh):
        return os.fsync(fh)

    def fsync(self, path, datasync, fh):
        print_with_time("Fsync %s(%d)" % (path, inode(path)))
        return os.fsync(fh)
        ### os.fdatasync is not available on MacOS
        if datasync != 0 and _system != "Darwin":
          return os.fdatasync(fh)
        else:
          return os.fsync(fh)

    def getattr(self, path, fh=None):
        st = os.lstat(path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
            'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    getxattr = None
    listxattr = None

    def link(self, target, source):
        return os.link(source, target)

    def mkdir(self, path, mode):
        os.mkdir(path, mode)
        print_with_time("Mkdir %s(%d)" % (path, inode(path)))

    def mknod(self, path, mode, dev):
        return os.mknod(path, mode, dev)

    def open(self, path, fip):
        return os.open(path, fip)

    def read(self, path, size, offset, fh):
        print_with_time("Read %s(%d) size=%d offset=%d" % (path, inode(path), size, offset))

        with self.rwlock:
            os.lseek(fh, offset, 0)
            data = os.read(fh, size)

        # if read is last round, save fileinfo
        if os.lstat(path).st_size == (size + offset):
            save_filelog(path)

        return data

    def readdir(self, path, fh):
        return ['.', '..'] + os.listdir(path)

    def readlink(self, path):
        return os.readlink(path)

    def release(self, path, fh):
        return os.close(fh)

    def rename(self, old, new):
        newpath = self.root + new
        os.rename(old, newpath)
        print_with_time("Rename %s to %s(%d)" % (old, newpath, inode(newpath)))

    def rmdir(self, path):
        print_with_time("Rmdir %s(%d)" % (path, inode(path)))
        return os.rmdir(path)

    def statfs(self, path):
        stv = os.statvfs(path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def symlink(self, target, source):
        return os.symlink(source, target)

    def truncate(self, path, length, fh=None):
        with open(path, 'r+') as f:
            f.truncate(length)

    def unlink(self, path):
        print_with_time("Delete %s(%d)" % (path, inode(path)))
        return os.unlink(path)

    def utimens(self, path, buf):
        return os.utime(path, buf)

    def write(self, path, data, offset, fh):
        print_with_time("Write %s(%d) datasize=%d offset=%d" % (path, inode(path), len(data), offset))

        with self.rwlock:
            os.lseek(fh, offset, 0)
            size = os.write(fh, data)

        # if write is last round, save fileinfo
        if os.lstat(path).st_size == (size + offset):
            dest = save_filelog(path)
            src = search_source_file(dest)
            # if source fileinfo is exist, save copy_log
            if src:
                save_copylog(src, dest)

        return size

def print_with_time(str):
    time = datetime.now()
    msec = "%03d" % (time.microsecond // 1000)
    print(time.strftime("%Y/%m/%d %H:%M:%S,") + msec + ' ' + str)

def inode(path):
    return os.stat(path).st_ino

def save_filelog(path):
    f = os.lstat(path)
    fd = os.open(path, os.O_RDONLY)
    content = os.read(fd, f.st_size)

    session = db.session()
    detected_file = session.query(File).filter(File.inode == f.st_ino).first()

    if detected_file:
        # Update file info
        detected_file.name = basename(path)
        detected_file.path = path
        detected_file.uid = f.st_uid
        detected_file.gid = f.st_gid
        detected_file.atime = datetime.fromtimestamp(f.st_atime)
        detected_file.mtime = datetime.fromtimestamp(f.st_mtime)
        detected_file.size = f.st_size
        detected_file.hash_value = hashlib.sha1(content).hexdigest()
        session.add(detected_file)
    else:
        # Create new file info
        new_file = File(
            inode = f.st_ino,
            name = basename(path),
            path = path,
            uid = f.st_uid,
            gid = f.st_gid,
            atime = datetime.fromtimestamp(f.st_atime),
            mtime = datetime.fromtimestamp(f.st_mtime),
            ctime = datetime.fromtimestamp(f.st_ctime),
            size = f.st_size,
            hash_value = hashlib.sha1(content).hexdigest()
        )
        session.add(new_file)

    # Get Create/Update file object
    data = File()
    for x in (session.dirty | session.new):
        data = x

    session.commit()

    saved_file = session.query(File).filter(File.inode == data.inode).first()
    session.close()

    return saved_file

def save_copylog(src, dest):
    session = db.session()
    new_copy_log = CopyLog(
        source = src,
        destination = dest,
        created_at = datetime.now()
    )
    session.add(new_copy_log)
    session.commit()

def search_source_file(file):
    session = db.session()
    source_file = session.query(File).filter(
        File.hash_value == file.hash_value,
        File.id != file.id,
        File.mtime < file.mtime
    ).order_by(File.atime.desc()).first()
    session.close()

    if source_file:
        return source_file
    else:
        return None


if __name__ == '__main__':
    if len(argv) != 3:
        print('usage: %s <root> <mountpoint>' % argv[0])
        exit(1)

    # logging.basicConfig(level=logging.DEBUG)

    fuse = FUSE(ReuseTrackFS(argv[1]), argv[2], foreground=True)
