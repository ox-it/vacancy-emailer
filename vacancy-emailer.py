#!/bin/env python3

from __future__ import print_function

import argparse
import datetime
import email.mime.multipart
import email.mime.text
import email.utils
import logging
import json
import os
import smtplib
import sys
import textwrap
import urllib.request

import dateutil.parser
from inlinestyler.utils import inline_css
from lxml import etree
from lxml.builder import E
import requests

logger = logging.getLogger(__name__)

class VacancyEmailer(object):
    def __init__(self, seen_before):
        self._seen_before = os.path.expanduser(seen_before) if seen_before else None

    @property
    def feed_url(self):
        return os.environ['FEED_URL']

    @property
    def email_from(self):
        return os.environ['EMAIL_FROM']

    @property
    def email_to(self):
        return os.environ['EMAIL_TO']

    @property
    def email_subject(self):
        return os.environ['EMAIL_SUBJECT']

    @property
    def smtp_server(self):
        return os.environ['SMTP_SERVER']

    @property
    def html_preamble(self):
        return etree.parse(open(os.environ['HTML_PREAMBLE_FILE'], 'rb')).getroot()

    @property
    def html_css(self):
        return open(os.environ['HTML_CSS_FILE'], 'rb').read().decode('utf-8')

    @property
    def text_preamble(self):
        return open(os.environ['TEXT_PREAMBLE_FILE'], 'rb').read().decode('utf-8')

    def __call__(self):
        vacancies = self.get_vacancies()

        current_vacancies = set(vacancies.xpath('/vacancies/vacancy/@id'))
        if self._seen_before and os.path.exists(self._seen_before):
            seen_vacancies = set(open(self._seen_before, 'r').read().split())
            new_vacancies = current_vacancies - seen_vacancies
        else:
            new_vacancies = set()

        html, text = self.generate_email_bodies(vacancies, new_vacancies)
        msg = self.compose_email(html, text)
        self.send_email(msg)

        if self._seen_before:
            with open(self._seen_before, 'w') as f:
                for vacancy_id in sorted(current_vacancies):
                    f.write('{}\n'.format(vacancy_id))

    def get_vacancies(self):
        return etree.parse(urllib.request.urlopen(self.feed_url))

    def generate_email_bodies(self, vacancies, new_vacancies):
        html_vacancies = E('div')
        html = E('html',
                 E('head', E('style', self.html_css, type='text/css')),
                 E('body', self.html_preamble, html_vacancies))
        
        text_body = [self.text_preamble]
        
        for i, vacancy in enumerate(vacancies.xpath('/vacancies/vacancy')):
            vacancy_id = vacancy.attrib['id']
            html_description = etree.fromstring(vacancy.xpath("description[@media_type='text/html']")[0].text,
                                                parser=etree.HTMLParser())[0][0]
            first_para = html_description.xpath(".//text()[normalize-space(.) and not(contains(., 'INTERNAL') or contains(., 'ADVERTISEMENT'))]")[0].strip()
            html_first_para = E('div', first_para, **{'class': 'description'})
            tags = []
            if 'INTERNAL' in html_description.text:
                tags.append('internal applicants only')
            if 'ADVERTISEMENT' in html_description.text:
                tags.append('re-advertisement')
            tags = ' ({0})'.format(', '.join(tags)) if tags else ''
            try:
                closes = dateutil.parser.parse(vacancy.find('closes').text)
            except Exception:
                closes, closes_soon = 'unknown', False
            else:
                closes_soon = (closes - datetime.datetime.now(datetime.timezone.utc)).total_seconds() < 3600 * 24 * 2
                closes = closes.strftime('%a, %d %b %Y, %I:%M %p')
            html_vacancy = E('div',
                E('h1', vacancy.find('label').text),
                E('div',
                  E('span', vacancy.find('salary').find('label').text, **{'class': 'salary'}),
                  '; closes: ',
                  E('span', closes, **{'class': 'closes' + (' closes-soon' if closes_soon else '')}),
                  tags,
                  **{'class': 'byline'}
                ),
                html_first_para,
                E('div',
                  E('a', u'More details\N{HORIZONTAL ELLIPSIS}', href=vacancy.find('webpage').text)),
                **{'class': 'vacancy'}
            )
            if vacancy_id in new_vacancies:
                html_vacancy[0].text += " "
                html_vacancy[0].append(E('span', '★ new', **{'class': 'new'}))
            html_vacancies.append(html_vacancy)
        
            text_body.extend([
                '_' * 70,
                u'\n\n',
                textwrap.fill('*' + vacancy.find('label').text + '*'),
                u'\n\n',
                vacancy.find('salary').find('label').text,
                u'\nCloses: ',
                closes,
                tags,
                u'\n\n',
                textwrap.fill(first_para),
                u'\n\n'
                u'More details: https://data.ox.ac.uk/v/',
                vacancy.attrib['id'],
                u'\n'
            ])
        
        html_body = inline_css(etree.tostring(html, method='html'))
        text_body = u''.join(text_body).encode('utf-8')
        
        return html_body, text_body

    def compose_email(self, html_body, text_body):
        msg = email.mime.multipart.MIMEMultipart('alternative')
        msg['Subject'] = self.email_subject
        msg['From'] = self.email_from
        msg['To'] =self. email_to
        msg.attach(email.mime.text.MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(email.mime.text.MIMEText(html_body, 'html', 'utf-8'))
        return msg

    def send_email(self, msg):
        s = smtplib.SMTP(self.smtp_server)
        s.sendmail(email.utils.parseaddr(self.email_from)[1],
                   email.utils.parseaddr(self.email_to)[1],
                   msg.as_string())
        s.quit()

class OnlyFirstWorkingDayOfWeekMixin(object):
    bank_holidays_json_url = 'https://www.gov.uk/bank-holidays.json'

    def __call__(self, *arg, **kwargs):
        bank_holidays = json.loads(requests.get(self.bank_holidays_json_url).text)
        bank_holidays = set(datetime.datetime.strptime(d['date'], "%Y-%m-%d").date()
                            for d in bank_holidays['england-and-wales']['events'])
        today = datetime.date.today()
        
        def working_day(d):
            return (d.weekday() < 5                            # Not a weekend
                and d not in bank_holidays                     # Not a bank holiday
                and not (d.month == 12 and 25 <= d.day <= 31)) # Not in Christmas closedown

        # Only send if today is actually a working day, and...
        if not working_day(today):
            logger.info("Today is not a working day; not continuing")
            return
        
        # Look back through the week. If any of those days was also a working day, stop now.
        for i in range(today.weekday(), 0, -1):
            previous_date = today - datetime.timedelta(i)
            if working_day(previous_date):
                logger.info("%s was a working day; not continuing", previous_date)
                return

        super(OnlyFirstWorkingDayOfWeekMixin, self).__call__(*arg, **kwargs)

class PrintEmailInsteadMixin(object):
    def send_email(self, msg):
        print(msg.as_string())

if __name__ == '__main__':
    argparser = argparse.ArgumentParser(
        description="Send emails about vacancies")
    argparser.add_argument('-l', '--log-level',
                           dest='loglevel', action='store',
                           help="Python logging level")
    argparser.add_argument('-d', '--dry-run',
                           dest='dry_run', action='store_true',
                           help="Print email instead of emailing it")
    argparser.add_argument('-w', '--only-first-working-day',
                           dest='first_working_day', action='store_true',
                           help="Only send if today is the first working day of the week")
    argparser.add_argument('-s', '--seen-before',
                           dest='seen_before', action='store',
                           help='File containing vacancies seen before')

    args = argparser.parse_args()
    if args.loglevel:
        try:
            logging.basicConfig(level=getattr(logging, args.loglevel.upper()))
        except AttributeError:
            sys.stderr.write("{0} is not a valid log level".format(args.loglevel.upper()))
            sys.exit(1)

    bases = (VacancyEmailer,)
    if args.first_working_day:
        bases = (OnlyFirstWorkingDayOfWeekMixin,) + bases
    if args.dry_run:
        bases = (PrintEmailInsteadMixin,) + bases

    cls = type('VacancyEmailer', bases, {})
    cls(seen_before=args.seen_before)()
