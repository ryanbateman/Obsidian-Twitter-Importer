import json
import os
import yaml
import re
from tqdm import tqdm
from datetime import datetime
from functools import reduce

# Load the configuration from config.yaml
with open('config.yaml', 'r') as config_file:
    config = yaml.safe_load(config_file)

# Extract configuration details
json_file = config['json_file']
output_dir = config['output_dir']
users_dir = config['users_dir']
properties = config['properties']

# Create the output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Createe the usres directory if it doesn't exist and is needed
if properties.get('create_user_files'):
    os.makedirs(users_dir, exist_ok=True)

# Function to sanitize file names
def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c in " ._-").rstrip()

# Function to quick reference nested dict elements
def deep_get(dictionary, keys, default=None):
    return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."), dictionary)


# Function to strip html bits
def strip_html(text):
    return re.sub(r"<.*?>", "", text)

# Function to format date
def format_date(date_str):
    try:
        date_obj = datetime.strptime(date_str,'%a %b %d %H:%M:%S +0000 %Y')
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        return date_str

# Function to format date time (this could be neater but, meh)
def format_date_time(date_str):
    try:
        date_obj = datetime.strptime(date_str,'%a %b %d %H:%M:%S +0000 %Y')
        return date_obj.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return date_str

# Function to generate daily note link based on a date string
def generate_daily_note_link(date_str):
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    #date_obj = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%fZ')
    year = date_obj.strftime('%Y')
    month_num = date_obj.strftime('%m')
    month_name = date_obj.strftime('%B')
    day_date = date_obj.strftime('%Y-%m-%d')
    day_name = date_obj.strftime('%A')
    return f"/Dailies/{day_date}.md"

def generate_tweet_date_file(id, created_date):
    date_obj = datetime.strptime(created_date,'%a %b %d %H:%M:%S +0000 %Y')
    year = date_obj.strftime('%Y')
    month_num = date_obj.strftime('%m')
    month_name = date_obj.strftime('%B')
    day_date = date_obj.strftime('%Y-%m-%d')
    day_name = date_obj.strftime('%A')
    day = date_obj.strftime('%d')
    return f"{year}/{month_num}/{day}/{id}.md"

# Function to properly capitalise strings
def format_string(s):
    return ' '.join(word.capitalize() for word in s.split('_'))

# Function to convery bool to symbols
def format_bool(value):
    return '✓' if value else '✗'


# Function to create markdown content for a bean
def create_markdown(tweet):
    content = []
    yaml_frontmatter = []

    # Process the tweet content
    content.append(f"> {tweet.get('full_text')}\n\n")

    if properties.get('include_retweets', False) and tweet.get('retweeted', False):
        return

    # TODO: Fill out all retweet metadata
    # Process each property based on the configuration
    if tweet.get('retweeted', False):
        yaml_frontmatter.append(f'retweeted: true')

    if tweet.get('in_reply_to_user_id', False):
        reply_to_id = tweet.get('in_reply_to_user_id', 'Unknown user id')
        reply_to_username = tweet.get('in_reply_to_screen_name', 'Unknown user name')
        yaml_frontmatter.append(f'replying to: [[{reply_to_username}]]')
        yaml_frontmatter.append(f'replying to tweet id: [[{reply_to_id}]]')
        if (properties.get('create_user_files', False)):
            user_file = os.path.join(users_dir, f"{reply_to_username}.md")
            with open(user_file, 'a', encoding='utf-8') as md_file:
                md_file.write(f'[[{tweet_id}.md]]\n')
    if len(user_mentions := deep_get(tweet, 'entities.user_mentions')) > 0:
        user_names_mentioned = [f"[[{user.get('screen_name')}]]" for user in user_mentions]
        yaml_frontmatter.append(f'users mentioned: {", ".join(user_names_mentioned)}"')
        



    created_date_time = format_date_time(tweet.get('created_at', ''))
    created_date = format_date(tweet.get('created_at', ''))
    if created_date_time != '':
        yaml_frontmatter.append(f'date: "{created_date_time}"')
        daily_note_link = generate_daily_note_link(created_date)
        content.append(
            f"Posted: [{created_date_time}]({daily_note_link})")
    
    yaml_frontmatter.append(f'favourite count: {tweet.get('favorite_count')}')
    yaml_frontmatter.append(f'retweet count: {tweet.get('retweet_count')}')
    yaml_frontmatter.append(f'source: {strip_html(tweet.get('source'))}')
    
    # Combine YAML frontmatter and content
    yaml_section = "---\n" + \
        "\n".join(yaml_frontmatter) + "\ntags: \n- twitter\n---\n"
    markdown_content = yaml_section + "\n".join(content)

    return markdown_content


def amend_markdown(makrown_file, bean):
    roasting_date = format_date(bean.get('roastingDate', ''))
    daily_note_link = generate_daily_note_link(roasting_date)
    weight = bean.get('weight', 0)
    cost = bean.get('cost', 0)

    with open(makrown_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        for i, line in enumerate(lines):
            if line.startswith("roasting_date:"):
                lines[i] = f'roasting_date: "{roasting_date}"\n'
            elif line.startswith("weight:"):
                lines[i] = f'weight: {weight}g\n'
            elif line.startswith("cost:"):
                lines[i] = f'cost: ₹{cost}\n'

        lines.append(f"| [{roasting_date}]({daily_note_link}) | {
                     weight}g | ₹{cost}|\n")

        markdown_content = ''.join(lines)

    return markdown_content


# Read the JSON file
with open(json_file, 'r', encoding='utf-8') as file:
    file_content = file.read()
    json_content = file_content.strip('window.YTD.tweets.part0 = ')
    data = json.loads(json_content)


# Process each tweet and create a markdown file
for tweet_array in tqdm(data):
    tweet = tweet_array.get('tweet')
    # print(f"Processing {tweet.get('id', 'Unknown tweet...?')}...")
    tweet_id = sanitize_filename(tweet.get('id', 'Unknown tweet'))
    markdown_file = os.path.join(output_dir, f"{generate_tweet_date_file(tweet_id, tweet.get('created_at'))}")

    # if os.path.exists(markdown_file):
    #     print(f"Appending history to {tweet_id}.md...")
    #     markdown_content = amend_markdown(markdown_file, tweet)
    # else:
    # print(f"Creating {tweet_id}.md...")
    markdown_content = create_markdown(tweet)
    os.makedirs(os.path.dirname(markdown_file), exist_ok=True)

    with open(markdown_file, 'w', encoding='utf-8') as md_file:
        md_file.write(markdown_content)

print(f"Markdown files created in '{output_dir}' directory.")