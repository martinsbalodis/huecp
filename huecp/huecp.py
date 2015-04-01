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
import tempfile

class HueClient(object):

    def __init__(self, host, username):
        self.host = host
        self.password = None
        self.username = username
        self.csrf_token = None

        # cookie file
        f = tempfile.NamedTemporaryFile(mode='w+b', delete=False)
        self.cookiefile = f.name
        f.close()

    def login(self):
        if self.password is None:
            password = getpass.getpass()
            self.password = password
        url = self.host+"accounts/login/"

        # first get CSRF token
        c = pycurl.Curl()
        self.c = c
        c.setopt(c.FOLLOWLOCATION, 0)
        c.setopt(c.URL, url)
        c.setopt(pycurl.COOKIEFILE, self.cookiefile)
        c.setopt(pycurl.COOKIEJAR, self.cookiefile)
        response = cStringIO.StringIO()
        c.setopt(c.WRITEFUNCTION, response.write)
        #c.setopt(c.VERBOSE,1)
        c.perform()
        status_code = c.getinfo(c.HTTP_CODE)
        if status_code != 200:
            logging.error("Failed to open login page")
            return False

        # get csrf token
        cookies = c.getinfo(pycurl.INFO_COOKIELIST)
        for cookie in cookies:
            cookie_data = cookie.split("\t")
            if cookie_data[5] == 'csrftoken':
                self.csrf_token = cookie_data[6]

        if self.csrf_token is None:
            logging.error("CSRF token not found in cookie")
            raise Exception("CSRF token not found in cookie")

        c.setopt(c.POST, 1)
        c.setopt(c.FOLLOWLOCATION, 0)
        c.setopt(c.URL, url)
        c.setopt(pycurl.COOKIEFILE, 'huecp-cookies-curl')
        c.setopt(pycurl.COOKIEJAR, self.cookiefile)
        c.setopt(c.POSTFIELDS, "username="+self.username+"&password="+self.password+"&csrfmiddlewaretoken="+self.csrf_token+"&next=/")
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

    def file_exists(self, remote_file):

        error = True
        while error:
            try:
                logging.info("checking whether file already exists "+remote_file)
                url = self.hueclient.host+'filebrowser/view/'+ remote_file
                c = self.hueclient.c
                c.setopt(c.URL, url)
                c.setopt(pycurl.COOKIEFILE, self.hueclient.cookiefile)
                response = cStringIO.StringIO()
                c.setopt(c.WRITEFUNCTION, response.write)
                c.setopt(pycurl.TIMEOUT, 10)
                c.perform()
                response = response.getvalue()
                status_code = c.getinfo(c.HTTP_CODE)
                error = False
            except:
                # try creating a new session
                self.hueclient.login()
                error = True

        file_path_in_response = remote_file
        if file_path_in_response not in response and status_code == 200:
            raise Exception("couldn't find file in response "+file_path_in_response)

        if status_code == 200:
            if file_path_in_response not in response:
                raise Exception("couldn't find file in response "+file_path_in_response)
            return True
        elif status_code == 500:
            if remote_file+" not found" not in response:
                raise Exception("couldn't find message that file is not found "+file_path_in_response)
            return False
        else:
           raise Exception("unknown status code "+str(status_code))

    def upload(self, local_file, remote_file, filename_regex):

        logging.info("uploading"+local_file+" to "+remote_file)

        # upload file if its upload is required
        if filename_regex is not None:
            r = re.compile(filename_regex)
            if r.match(local_file) is None:
                logging.info("Ignoring file by regex: "+local_file)
                return


        # first check if file does not exist
        if self.file_exists(remote_file) == True:

            logging.warning("Remote file already exists: "+remote_file)
            return True

        logging.info("Started file upload: "+remote_file)

        dest_dir = os.path.dirname(remote_file)+"/"

        url = self.hueclient.host+'filebrowser/upload/file?dest='+dest_dir

        data = [
            ("dest", dest_dir),
            ("hdfs_file", (pycurl.FORM_FILE, local_file, pycurl.FORM_FILENAME, ntpath.basename(local_file)))
        ]

        c = self.hueclient.c
        c.setopt(c.POST, 1)
        c.setopt(c.URL, url)
        c.setopt(pycurl.COOKIEFILE, self.hueclient.cookiefile)
        c.setopt(pycurl.TIMEOUT, 300)
        c.setopt(c.HTTPPOST, data)
        response = cStringIO.StringIO()
        #c.setopt(c.VERBOSE,1)
        c.setopt(c.WRITEFUNCTION, response.write)
        c.setopt(pycurl.HTTPHEADER, ['X-CSRFToken: '+self.hueclient.csrf_token])
        c.perform()

        status_code = c.getinfo(c.HTTP_CODE)
        if status_code != 200:
            logging.info("Upload failed: "+local_file)
            raise Exception("Upload fail")


        try:
            import json
            result = json.loads(response.getvalue())
            logging.info("File upload status: "+str(result['status']))
        except Exception:
            pass

        logging.info("Upload finished: "+local_file)

def get_upload_file_paths(files, dest_dir):

    result_files = []

    for filename in files:
        # a file was given
        if os.path.isfile(filename):
            local_file = filename
            filename = os.path.basename(filename)
            remote_file = os.path.join(dest_dir, filename)
            result_files.append((local_file, remote_file))
            continue

        # a directory was given
        basedir = os.path.dirname(os.path.realpath(filename))
        for root, subdirs, files2 in os.walk(filename):
            for filename2 in files2:
                local_file = os.path.join(root, filename2)
                destdir_file_local = local_file[len(basedir):]
                remote_file = dest_dir+destdir_file_local
                result_files.append((local_file, remote_file))
    return result_files

def main(options, files):

    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.DEBUG)

    filename_regex = None
    if hasattr(options, "filename_regex"):
        filename_regex = options.filename_regex

    client = HueClient(options.host, options.username)
    if client.login():
        fb_client = HueFileBrowserClient(client)

        file_paths = get_upload_file_paths(files, options.dest_dir)
        for path in file_paths:
            logging.info("Will be uploading "+path[0]+" to "+path[1])

        for path in file_paths:
            fb_client.upload(path[0], path[1], filename_regex)

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