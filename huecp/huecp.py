#!/usr/bin/env python
"""huecp - commandline tool to copy files to HUE"""
import os

import sys
import getpass
import logging
from optparse import OptionParser
import cStringIO
import pycurl
import ntpath
import re
import urllib

class HueClient(object):

    def __init__(self, host):
        self.host = host
        self.c = pycurl.Curl()

    def login(self, username):
        password = getpass.getpass()
        url = self.host+"accounts/login/"

        c = self.c
        c.setopt(c.POST, 1)
        c.setopt(c.FOLLOWLOCATION, 0)
        c.setopt(c.URL, url)
        c.setopt(pycurl.COOKIEFILE, 'huecp-cookies-curl')
        c.setopt(pycurl.COOKIEFILE, 'huecp-cookies-curl')
        c.setopt(c.POSTFIELDS, "username="+username+"&password="+password)
        response = cStringIO.StringIO()
        c.setopt(c.WRITEFUNCTION, response.write)
        #c.setopt(c.VERBOSE,1)
        c.perform()
        status_code = c.getinfo(c.HTTP_CODE)

        if status_code == 302:
            return True
        else:
            logging.error("Login failed")
            return False

    def close(self):
        self.c.close()

class HueFileBrowserClient(object):

    def __init__(self, hueclient):
        self.hueclient = hueclient

    def file_exists(self, dest_dir, filename):

        file_path = dest_dir+filename
        url = self.hueclient.host+'filebrowser/view/'+ file_path
        c = self.hueclient.c
        c.setopt(c.URL, url)
        c.setopt(pycurl.COOKIEFILE, '/tmp/huecp-cookies-curl')
        c.setopt(pycurl.COOKIEFILE, '/tmp/huecp-cookies-curl')
        response = cStringIO.StringIO()
        c.setopt(c.WRITEFUNCTION, response.write)
        c.perform()
        response = response.getvalue()
        status_code = c.getinfo(c.HTTP_CODE)

        file_path_in_response = dest_dir+urllib.quote_plus(filename)
        if file_path_in_response not in response and status_code == 200:
            raise Exception("couldn't find file in response "+file_path_in_response)

        if status_code == 200:
            if file_path_in_response not in response:
                raise Exception("couldn't find file in response "+file_path_in_response)
            return True
        elif status_code == 500:
            if dest_dir+filename+" not found" not in response:
                raise Exception("couldn't find message that file is not found "+file_path_in_response)
            return False
        else:
           raise Exception("unknown status code "+str(status_code))

    def upload(self, dest_dir, filename, filename_regex):

        if not dest_dir.endswith("/"):
            dest_dir = dest_dir+"/"

        if filename.endswith("/"):
            filename = filename[:-1]

        _filename = ntpath.basename(filename)

        # recursively import files from subdirectories
        if os.path.isdir(filename):
            for fn in os.listdir(filename):
                if fn == "." or fn == "..":
                    return
                self.upload(dest_dir+_filename+'/', filename+'/'+fn, filename_regex)
            return

        # upload file if its upload is required
        if filename_regex is not None:
            r = re.compile(filename_regex)
            if r.match(filename) is None:
                logging.info("Ignoring file by regex: "+filename)
                return


        # first check if file does not exist
        if self.file_exists(dest_dir, _filename) == True:

            logging.warning("File already exists: "+_filename)
            return True

        logging.info("Started file upload: "+_filename)

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
        #c.setopt(c.VERBOSE,1)
        c.setopt(c.WRITEFUNCTION, response.write)
        c.perform()

        try:
            import json
            result = json.loads(response.getvalue())
            logging.info("File upload status: "+str(result['status']))
        except Exception:
            pass

        print response.getvalue()

def main(options, files):

    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.DEBUG)

    filename_regex = None
    if hasattr(options, "filename_regex"):
        filename_regex = options.filename_regex

    client = HueClient(options.host)
    if client.login(options.username):
        fb_client = HueFileBrowserClient(client)
        for filename in files:
            logging.info("Will be uploading "+filename)
        for filename in files:
            fb_client.upload(options.dest_dir, filename, filename_regex)

        logging.info("Finished")
        client.close()

def run():

    parser = OptionParser(usage="%prog [options] file (file ...)")
    parser.add_option("-u", "--username", dest="username", help="Hue user username")
    parser.add_option("-d", "--destination", dest="dest_dir", help="Destination directory")
    parser.add_option("-a", "--hue-access-point", dest="host", help="HUE access point: http://hue.com:8888/")
    parser.add_option("-r", "--filename-regex", dest="filename_regex", help="only upload files matching regex for example .*\.gz")
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