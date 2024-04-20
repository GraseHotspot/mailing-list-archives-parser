import re


def mask_all_emails(text):

    emails = sorted(re.findall(r"[A-Za-z0-9\.\-+_]+@[A-Za-z0-9\.\-+_]+\.[A-Za-z]+", text), key=len)
    if emails:
        emails = list(set(emails))
        emails.reverse()
    # @TODO add whitelist?
    replacements = []
    for email in emails:
        text = text.replace(email, mask_email(email))

    return text

def mask_email(email):
    user, domain = email.split('@', 2)
    user = user[0:2] + "***" + user[-1]
    return f"{user}@{domain}"


def make_id_from_email(email):
    if '<' in email:
        email = re.search('<(.+)>', email).group(1)
    email = mask_email(email).replace('*', '_')
    email = str(email).replace('@', '_at_')
    email = re.sub('[<>\(\)\.\s]+', '_', email)
    email = re.sub('\W+', '', email)
    return email.lower()    


def mask_from(from_text, replace_at='<span>@</span>'):
    if '<' in from_text:
        parts = re.search('(.*)<(.+)>', from_text)
        name = parts.group(1)
        email = mask_email(parts.group(2)).replace('@', replace_at)
        return f"{name}<{email}>"
    return mask_email(from_text).replace('@', replace_at)
    