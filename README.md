# huecp
This program automates file copying from local disk to Cloudera HUE via HUE web page.

Usage:
```sh
./huecp.py -u <username> -d <HDFS directory> -a http://<hue>:8888/ <files>
```

Example:
```sh
./huecp.py -u martinsbalodis -d /user/martinsbalodis/lv-domains -a http://1.2.3.4:8888/ /media/data/heritrix-running-jobs/lv-domains/latest/warcs/*.warc.gz
```
