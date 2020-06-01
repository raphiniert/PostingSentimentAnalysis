# PostingStentimentAnalysis

This project provides a command line interface, written in python3, to extract postings from https://derstandard.at (only derstandard.at, other online newspapers are not supported), to provide basic statistics and to apply a sentiment analysis to the extracted data.
It's part of the seminar 'Der "Historikerbericht" und die Historisierung der FPÖ' (see https://ufind.univie.ac.at/de/course.html?lv=070086&semester=2020S) held at the University of Vienna. 
The coding style for this project is quick'n'dirty.
It's not performance optimized and there are no unit tests, sanity or security checks, but it gets the job done.
I highly recommend to create backups of the resulting sqlite database files if you are done crawling. 

## prerequisites

* Working python ≥ 3.7 installation (https://www.python.org/downloads/)
* Google Chrome installed (https://www.google.com/chrome/)
* Downloaded `chromedriver` file matching the installed Chrome version (https://sites.google.com/a/chromium.org/chromedriver/downloads)

### download project and copy chromedriver
If you are familiar with git and the command line run:
```shell script
git clone https://github.com/raphiniert/PostingStentimentAnalysis.git
cd PostingStentimentAnalysis
mkdir bin
mkdir log
cp path/to/chromedriver bin/chromedriver
```

In case you aren't familiar with the command line download this project as a .zip file,
open it and create two folders, one named `bin` and one named `log`.
Copy the previously downloaded file `chromedrive` into the `bin` folder.
Unfortunately, you have to get familiar with the command line anyways to use this tool.
If you don't know how to enter a folder in a terminal, let me google that for you (https://lmgtfy.com/?q=enter+a+folder+in+terminal&s=d).

### setup virtual environment and install dependencies

Open a terminal, enter the project folder an execute following steps:

```shell script
python3 -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Verify if everything worked by running:

```shell script
python crawl.py -h
```

If you see the following output, you're good to go.

```shell script
usage: crawl.py [-h] [--continue-article CONTINUE_ARTICLE] [--retries RETRIES]
                [--verbose] [--no-headless]

optional arguments:
  -h, --help            show this help message and exit
  --continue-article CONTINUE_ARTICLE
                        continue crawling with article
  --retries RETRIES     max retries per article
  --verbose             increase output verbosity
  --no-headless         don't run chrome headless
```

## crawl postings
Specify urls to look for postings in the url_list within the `crawl.py` file:
```python
# urls to crawl
url_list = [
    "https://www.derstandard.at/story/2000112608982/fpoe-praesentiert-historikerbericht",
    "https://www.derstandard.at/story/2000114104569/fpoe-historikerberichtexperten-bewerten-blaues-papier",
    "Place your url here",  # add a comment if you like
    "And another one here",
]
```

### usage

Make sure the virtual environment is activated before you run the folloing code.
You should see (venv) at somewhere in your terminal's current line.
Activate it by entering the project folder and run:
```shell script
. venv/bin/activate
```

After you're done you can just close the terminal or deactivate it by running:
```shell script
deactivate
```

After specifying the urls run the python script:
```shell script
python crawl.py
```

This command creates a logfile, which is stored inside the `log` folder.
The resulting sqlite (see https://www.sqlite.org) database gets stored in the `postings.db` file.
To access the raw data I suggest using your database tool of choice (most common tools support sqlite databases).
If no such tool comes to your mind you could try using DBeaver (https://dbeaver.io).

Show help
```shell script
python crawl.py --help
```

Specify number of retries per article before article gets skipped.
Sometimes errors occur and there is a variaty of reasons for that.
The tool automatically retries 10 times to continue crawling, but you can modify that value by adding the following argument. 
```shell script
python crawl.py --retries 50
```

In case something went wrong, you can continue crawling a specific article with the last successfully crawled posting.
To do so run:
```shell script
python crawl.py --continue-article 1
```

Increase output verbosity to show detailed log messages (you might want to try this if an article fails again and again to see where exactly the error occurs).
```shell script
python crawl.py --verbose
```

By default chrome runs in headless mode.
That means you want see the web browser running, but if you wish to see the browser you could by adding the following argument (this slows down the process).
```shell script
python crawl.py --no-headless
```

#### example
Continue crawling for the second article with increased verbosity
```shell script
python crawl.py --retries 50 --continue-article 2 --verbose
```

## statistics

### custom sql queries
you can run every sql query you can think of on the data.
The database structure is simple.
There are four tables. (1) Articles, (2) Postings, (3) Users and (4) PostingRatings.
A posting belongs to an article and is assigned to a user (except for deleted users).
PostingRatings handles the many-to-many relationship of users rating postings.

#### example
Query users and the amount of postings for article 1 ordered by the 
```sqlite
select users.user_name, count(p.posting_id) cp
from users
         inner join postings p on users.user_id = p.user_id
where p.article_id = 1
group by users.user_name
order by cp desc;
```

### pre defined statistics

TODO: print most common and usefuly stats, such as total postings, ratings and users per article, users posting in both articles etc.
```shell script
python statistics.py
```

## Sentiment Analysis

TODO

## troubleshooting

#### `SyntaxError: invalid syntax` or `ModuleNotFoundError: No module named 'selenium'`
Make sure your virtual environment is enabled.
You can enable it by running:
```shell script
. venv/bin/activate
```

#### `selenium.common.exceptions.WebDriverException: Message: 'chromedriver' executable needs to be in PATH.`
Make sure the `chromedriver` file is located in the `bin` folder within the project folder.
