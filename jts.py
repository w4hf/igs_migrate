import requests
import urllib3
import csv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ###################################################### PLEASE EDIT ONLY THIS BLOCK
# Define the Ansible Tower URL, username, password, and job template ID
tower_fqdn = 'tower.example.com'
tower_url = 'https://' + tower_fqdn
tower_username = "admin"
tower_password = "password"
#

tower_results_dir = './'

# # #####################################################################################


def extract_jt_details(csv, jt_name, jt_org):
    print(f'  --  Extracting details of JT "{jt_name}" | Org : "{jt_org}"')
    # Get JT pages count
    try:
        r = requests.get(tower_url + '/api/v2/job_templates/' + jt_name + '++' + jt_org + '/', auth=(tower_username, tower_password),
                     verify=False)
    except Exception as err:
        print(f'Error extracting JT {jt_name} | Org : {jt_org} |Error : {err}')

    jt_page = r.json()
    if r.status_code == 200 :
        if jt_page['type'] == 'job_template':
            jt_play = jt_page['playbook']
            print(f'        |__  JT "{jt_name}" | Playbook : "{jt_play}"')
            if jt_page['related']['project']:
                p = requests.get(tower_url + jt_page['related']['project'], auth=(tower_username, tower_password),
                         verify=False)
                project_page = p.json()
                project_name = project_page['name']
                project_url = project_page['scm_url']

                print(f'        |__  JT "{jt_name}" | Project : "{project_name}"')
                print(f'        |__  JT "{jt_name}" | Git URL : "{project_url}"')
            else:
                project_url = 'N/A'
                project_name = 'N/A'

            result = f'{jt_org};{jt_name};{project_url};{project_name}'
            csv.write(result + "\n")

    if r.status_code > 299:
        print(f'  !!  ERROR extracting JT {jt_name} | Org : {jt_org} ')
        result = f'{jt_org};{jt_name};ERROR;ERROR'
        csv.write(result + "\n")


# jts = [
#     {
#         'name': 'Demo Job Template',
#         'org': 'Default'
#     },
#     {
#         'name': 'Remediate Low Disk Space',
#         'org': 'Default'
#     }
# ]

with open('jts.csv', newline='') as jts_file:
    jts = list(csv.reader(jts_file, delimiter=';', quotechar='|'))

# Write csv dump file header
csv_file = open(tower_results_dir + '/jts_and_projects.csv', "w")
csv_file.write('Organization;Job Template Name;Git URL;Playbook;\n')

for jt in jts:
    extract_jt_details(csv_file, jt[0], jt[1])

csv_file.close()
