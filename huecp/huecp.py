#!/usr/bin/env python
"""huecp - commandline tool to copy files to HUE"""

import sys
import requests
import getpass
import logging
from optparse import OptionParser

# patch guess_filename function
# hue fails if it receives full path to file as filename
from requests import models
import ntpath
def guess_filename_replacement(obj):
    """Tries to guess the filename of the given object."""
    name = getattr(obj, 'name', None)
    if name and name[0] != '<' and name[-1] != '>':
        return ntpath.basename(name)
models.guess_filename = guess_filename_replacement


class HueClient(object):

    def __init__(self, host):
        self.host = host

    def login(self, username):
        password = getpass.getpass()

        data = {'username': username, 'password': password, 'next': '/'}
        url = self.host+"accounts/login/"
        r = requests.post(url, data=data, allow_redirects=False)

        if r.status_code != 302:
            logging.info("Login failed")
            return False

        self.session_cookies = r.cookies

        return True

class HueFileBrowserClient(object):

    def __init__(self, hueclient):
        self.hueclient = hueclient

    def upload(self, dest_dir, filename):
        url = self.hueclient.host+'filebrowser/upload/file?dest='+dest_dir

        files = {'hdfs_file': open(filename, 'rb', 4096)}
        data = {
            'dest':dest_dir
        }

        r = requests.post(url, files=files, data=data, cookies=self.hueclient.session_cookies)
        print r.content

def main(options, files):

    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.DEBUG)

    client = HueClient(options.host)
    if client.login(options.username):
        fb_client = HueFileBrowserClient(client)
        for filename in files:
            fb_client.upload(options.dest_dir, filename)

def run():

    parser = OptionParser(usage="%prog [options] file (file ...)")
    parser.add_option("-u", "--username", dest="username", help="Hue user username")
    parser.add_option("-d", "--destination", dest="dest_dir", help="Destination directory")
    parser.add_option("-a", "--hue-access-point", dest="host", help="HUE access point: http://hue.com:8888/")
    parser.set_defaults(username=None, dest_dir=None)

    (options, args) = parser.parse_args()

    if not options.dest_dir:
        parser.error('Destination directory not given')

    if not options.username:
        parser.error('Username not given')

    if not options.host:
        parser.error('Hue access point not given')

    sys.exit(main(options, args))

if __name__ == '__main__':
    run()