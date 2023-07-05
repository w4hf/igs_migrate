import json
import os
import sys
import requests
import urllib3
import urllib.parse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ###################################################### PLEASE EDIT ONLY THIS BLOCK
# Define the Ansible Tower URL, username, password, and job template ID
tower_fqdn = 'tower.example.com'
tower_url = 'https://' + tower_fqdn
tower_username = "admin"
tower_password = "password"

# Define AAP 2 URL, username, password, and job template ID
aap_fqdn = 'aap2.example.com'
aap_url = 'https://' + aap_fqdn
aap_username = "admin"
aap_password = "password"

# # #####################################################################################


class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open("igs_migration.log", "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        # this flush method is needed for python 3 compatibility.
        # this handles the flush command by doing nothing.
        pass


sys.stdout = Logger()


def extract_tower_job_template():
    # Get JT pages count
    r = requests.get(tower_url + '/api/v2/job_templates?page=1&page_size=200', auth=(tower_username, tower_password),
                     verify=False)
    jt_page1 = r.json()
    jt_count = jt_page1['count']
    jt_pages_count = jt_count // 200 + bool(jt_count % 200)
    print(f'Extracting {jt_count} Job Templates from {jt_pages_count} page(s) ...')

    # Write csv dump file header
    csv_file = open(tower_results_dir + '/job_templates.csv', "w")
    csv_file.write('Job Template ID;Organization;Job Template Name;Instance Group;IG Count;\n')

    # Loop through each page
    for x in range(1, (jt_pages_count + 1)):
        print(f' ---- Extracting Job templates from page number {x} ...')
        req = requests.get(tower_url + '/api/v2/job_templates?page=' + str(x) + '&page_size=200',
                           auth=(tower_username, tower_password), verify=False)
        jt_page = req.json()

        # Extract JT details
        for jt in jt_page['results']:
            # Get JT ID
            jt_id = jt['id']
            print(f' -------- Extracting Details of Job templates with ID {jt_id} ...')

            # Get JT Name
            jt_name = jt['name']

            # Get JT Org
            if jt['organization']:
                jt_org = jt['summary_fields']['organization']['name']
            else:
                jt_org = 'Null'

            # Get JT Instance Group
            print(f' ------------ Extracting Instance Group of Job templates with ID {jt_id} ...')
            ig_req = requests.get(
                tower_url + '/api/v2/job_templates/' + str(jt_id) + '/instance_groups/?&page_size=200',
                auth=(tower_username, tower_password), verify=False)
            ig_page = ig_req.json()
            ig_count = ig_page['count']
            ig_list = list()
            for ig in ig_page['results']:
                if ig['type'] == 'instance_group':
                    ig_list.append({'name': ig['name'], 'id': ig['id']})

            # Write result to CSV file
            result = str(jt_id) + ';' + jt_org + ';' + jt_name + ';' + str(ig_list) + ';' + str(ig_count)
            csv_file.write(result + "\n")

            # Append to result var
            jt_item = {'id': jt_id, 'name': jt_name, 'org': jt_org, 'ig_count': ig_count, 'igs': ig_list}
            tower_job_templates.append(jt_item)

    # json_result_file.write(tower_job_templates)
    with open(tower_results_dir + '/job_templates.json', "w") as fp:
        json.dump(tower_job_templates, fp, indent=4)
    print(f'Extraction finished from {tower_fqdn}')

    csv_file.close()


def extract_igs(url, username, password):
    igs_map = dict()
    u = url + '/api/v2/instance_groups/'
    ig_req = requests.get(u + '?&page_size=200', auth=(username, password), verify=False)
    ig_page = ig_req.json()
    for ig in ig_page['results']:
        igs_map[ig['name']] = ig['id']
    return igs_map


def create_igs_in_aap():
    print('Duplicating Tower IGs into AAP...')
    for ig in tower_igs_ids.keys():
        print(' ---- Duplicating the IG ' + ig + ' into AAP...')
        payload = {
            "name": ig,
            "is_container_group": 'false',
            #"credential": 'null',
            "policy_instance_percentage": 0,
            "policy_instance_minimum": 0,
            "policy_instance_list": [],
            "pod_spec_override": ""
        }
        ig_rul = aap_url + '/api/v2/instance_groups/'
        response = requests.post(ig_rul, json=payload, auth=(aap_username, aap_password), verify=False)
        if 200 <= response.status_code <= 299:
            print(' -------- SUCCESS : Creating IG "' + ig + '" successful')
        else:
            print(' -------- FAIL : Creating IG "' + ig + '" failed with error : ' + str(
                response.status_code) + " / " + response.content.decode())


def patch_job_template():
    print(f"Patching Job Templates on {aap_fqdn}")
    for jt in tower_job_templates:
        # Build named url
        print(f" ---- Treating Job Template {jt['name']}")
        if jt['org'] != 'Null':
            jt_url = aap_url + '/api/v2/job_templates/' + urllib.parse.quote(
                jt['name'] + '++' + jt['org'] + '/instance_groups/')

            for jt_ig in jt['igs']:
                # Define the payload for the POST request
                payload = {
                    "id": aap_igs_ids[jt_ig['name']]
                }

                # Send a POST request to the job template endpoint with the payload
                response = requests.post(jt_url, json=payload, auth=(aap_username, aap_password), verify=False)
                if 200 <= response.status_code <= 299:
                    print(' -------- SUCCESS : Setting IG of JT "' + jt['name'] + '" to "' + jt_ig[
                        'name'] + '" successful')
                else:
                    print(' -------- FAIL : Setting IG of JT "' + jt['name'] + '" to "' + jt_ig[
                        'name'] + '" failed with error : ' + str(
                        response.status_code) + " / " + response.content.decode())
    print(f"Patching finished on {aap_fqdn}")

# MAIN
print('')
print('########################################################################################')

# Create Result Dir
tower_results_dir = 'dump_tower_' + tower_fqdn.replace(".", "_").lower()
resultDirExist = os.path.exists(tower_results_dir)
if not resultDirExist:
    os.makedirs(tower_results_dir)

# aap_results_dir = 'results_aap_' + aap_fqdn.replace(".", "_").lower()
# resultDirExist = os.path.exists(aap_results_dir)
# if not resultDirExist:
#     os.makedirs(aap_results_dir)

# Init backup var
tower_job_templates = list()

# Backup IGs of Tower
tower_igs_ids = extract_igs(tower_url, tower_username, tower_password)
with open(tower_results_dir + '/igs_with_ids.json', "w") as fp:
    json.dump(tower_igs_ids, fp, indent=4)

# Extract IG IDs in new AAP
aap_igs_ids = extract_igs(aap_url, aap_username, aap_password)


extract_tower_job_template()
create_igs_in_aap()
patch_job_template()
print('')
print('########################################################################################')
