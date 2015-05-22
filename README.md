# Vacancy emailer

A small script to send an email of current vacancies. Supports dry-runs and
only sending an email on the first working day of the week (i.e. not a weekend,
a bank holiday, or during the (IT Services) Christmas close-down).

You'll need to install its dependencies listed in `requirements.txt` using e.g.:

    $ pip install -r requirements.txt

Execute it with `-h` or `--help` for details of command-line options.

Dy default, it expects various things in its environment. See the sample
`example-env.sh` for details of what needs to be available. You can probably
tweak this example for your own purposes to get started quickly.

Once you've got an environment ready, use e.g.:

    $ source your-env.sh
    $ python vacancy-emailer.py

Once you're happy, why not stick it in your crontab?

