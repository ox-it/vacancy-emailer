# The URL of a vacancy feed in XML format from data.ox.ac.uk
# This one is for IT Services, but you can change the ID on the end for
# another department
export FEED_URL=https://data.ox.ac.uk/feeds/all-vacancies/31337175.xml

# These are filenames that contain content used to create the emails. The
# HTML preamble must be a single XML element from HTML (but without an
# XHTML namespace).
export HTML_PREAMBLE_FILE=preamble.html
export TEXT_PREAMBLE_FILE=preamble.txt
export HTML_CSS_FILE=email.css

# This is the subject line of the email.
export EMAIL_SUBJECT="Current Vacancies"

# This is who the email should appear to come from.
export EMAIL_FROM="Do Not Reply <blackhole@ox.ac.uk>"

# And where it should be sent. This probably wants to be a mailing list
# to which the address above is subscribed.
export EMAIL_TO="Department of Muggle Studies <muggle-studies@maillist.ox.ac.uk>"

# And the SMTP server to use. If you're within the Oxford network, this
# default will work fine. If you're without, you'll have to find your own.
export SMTP_SERVER=smtp.ox.ac.uk
