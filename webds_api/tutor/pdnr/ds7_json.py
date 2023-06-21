import json

from numpy import array


# Reading
# =======
def parse_json_data(input: str or dict):
    if isinstance(input, str):
        json_file = open(input, 'r')
        json_data = json.load(json_file)
        json_file.close()
    else:
        json_data = input
    metadata = json_data['metadata']
    collections = {}
    for index, collection in enumerate(json_data['collections']):
        image_list = []
        hybridx_list = []
        hybridy_list = []
        for report in collection:
            image_list.append(report[1]['image'])
            hybridx_list.append(report[1]['hybridx'])
            hybridy_list.append(report[1]['hybridy'])
        image_array = array(image_list)
        hybridx_array = array(hybridx_list)
        hybridy_array = array(hybridy_list)
        collections['dataset{}'.format(index)] = (image_array, hybridx_array, hybridy_array)
    return metadata, collections

# Writing
# =======
