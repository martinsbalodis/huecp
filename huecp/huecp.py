#!/usr/bin/env python
"""huecp - commandline tool to copy files to HUE"""

import sys
import getpass
import logging
from optparse import OptionParser
import cStringIO
import pycurl
import ntpath


class HueClient(object):

    def __init__(self, host):
        self.host = host
        self.c = pycurl.Curl()

    def login(self, username):
        password = getpass.getpass()
        url = self.host+"accounts/login/"

        c = self.c
        c.setopt(c.POST, 1)
        c.setopt(c.FOLLOWLOCATION, 1)
        c.setopt(c.URL, url)
        c.setopt(pycurl.COOKIEFILE, 'huecp-cookies-curl')
        c.setopt(pycurl.COOKIEFILE, 'huecp-cookies-curl')
        c.setopt(c.POSTFIELDS, "username="+username+"&password="+password)
        response = cStringIO.StringIO()
        c.setopt(c.WRITEFUNCTION, response.write)
        c.perform()

        # success :/
        return True

    def close(self):
        self.c.close()

class HueFileBrowserClient(object):

    def __init__(self, hueclient):
        self.hueclient = hueclient

    def upload(self, dest_dir, filename):
        url = self.hueclient.host+'filebrowser/upload/file?dest='+dest_dir

        data = [
            ("dest", dest_dir),
            ("hdfs_file", (pycurl.FORM_FILE, filename, pycurl.FORM_FILENAME, ntpath.basename(filename)))
        ]

        c = self.hueclient.c
        c.setopt(c.POST, 1)
        c.setopt(c.URL, url)
        c.setopt(pycurl.COOKIEFILE, '/tmp/huecp-cookies-curl')
        c.setopt(pycurl.COOKIEFILE, '/tmp/huecp-cookies-curl')
        c.setopt(c.HTTPPOST, data)
        response = cStringIO.StringIO()
        c.setopt(c.VERBOSE,1)
        c.setopt(c.WRITEFUNCTION, response.write)
        c.perform()

def main(options, files):

    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.DEBUG)

    client = HueClient(options.host)
    if client.login(options.username):
        fb_client = HueFileBrowserClient(client)
        for filename in files:
            fb_client.upload(options.dest_dir, filename)

        client.close()

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