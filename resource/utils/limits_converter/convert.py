import sys
import json
import os
import re
import numpy as np
from os.path import isfile, join, exists
import xml.etree.ElementTree as ET

LIMIT_INPUT = "Recipe_input.json"
RECIPE_OUTPUT = "Recipe.json"
INDENT = None

def ConvertData(t, data, dimesion=None):
    if t == "int[]":
        value = list(map(int, data.split(",")))
    elif t == "int":
        value = int(data)
    elif t == "double":
        value = float(data)
    elif t == "double[]":
        value = list(map(float, data.split(",")))
    elif t == "string":
        value = data.replace("\"", "")
    elif t == "string[]":
        value = data.replace(" ", "").replace("\"", "").split(",")
    elif t == "string[][]":
        ###print(dimesion)
        dimension = re.findall(r'(?<=\[)\w+', dimesion)
        ####print(dimension[0], dimension[1])
        value = data.replace("\"", "").split(",")
        
        ### if test limit size not match
        row = int(dimension[0])
        column = int(dimension[1])
        total = row*column
        if (len(value) != total):
            value.extend(value[0:total - len(value)])

        arr2d = np.reshape(value, (-1, column))
        value = arr2d.tolist()
        ####print(arr2d)
    else:
        value = data

    return value
    
def ConvertLimit():
    recipe = {}
    recipe["limits"] = {}
    
    tree = ET.parse('Recipe.xml')
    root = tree.getroot()
    
    for test in root:
        if test.tag == 'test':
            ###print(test.tag, test.attrib)
            for sub1 in test:
                scriptname = test.get('scriptname')
                if sub1.tag == 'metadata':
                    metadata = sub1
                    dataname = metadata.get('name')
                    print(dataname)
                    metadescription = metadata.get('description')
                    recipe["limits"][dataname] = {}
                    recipe["limits"][dataname]["name"] = scriptname
                    recipe["limits"][dataname]["description"] = metadescription
                    recipe["limits"][dataname]["parameters"] = {}
                    for sub2 in metadata:
                        if sub2.tag == "parameter":
                            parameter = sub2
                            pname = parameter.get('name')
                            ptype = parameter.get('type')
                            pdes = parameter.get('description')
                            default = parameter.get('default')
                            ###print(parameter.tag, parameter.attrib)
                            ###print("--[name       ]", pname)
                            ###print("--[type       ]", ptype)
                            ###print("--[description]", pdes)
                            
                            recipe["limits"][dataname]["parameters"][pname] = {}
                            recipe["limits"][dataname]["parameters"][pname]["type"] = ptype
                            recipe["limits"][dataname]["parameters"][pname]["description"] = pdes
                            
                            for sub3 in parameter:
                                if sub3.tag == 'default':
                                    recipe["limits"][dataname]["parameters"][pname]["value"] = ConvertData(ptype, sub3.text)
                            
                if sub1.tag == 'input':
                    input = sub1
                    for sub2 in input:
                        arg = sub2
                        name = arg.get('name')
                        atype = arg.get('type')
                        value = arg.text
                        ###print("**[name       ]", name)
                        ###print("**[type       ]", atype)
                        ###print("**[value      ]", value)
                  
                        value = ConvertData(recipe["limits"][dataname]["parameters"][name]["type"], value, atype)
                        recipe["limits"][dataname]["parameters"][name]["value"] = value

    with open(RECIPE_OUTPUT, 'w') as f:
        json.dump(recipe, f, indent=INDENT)

    print("\n -- Success convert limits to Recipe.json --")
                            

def WriteToRecipe(data, file):
    with open(file, 'w') as f:
        json.dump(data, f, indent=INDENT)

def MergeRecipe(irecipe, limit):
    if exists(irecipe):
        with open(irecipe) as recipe_file:
            i = json.load(recipe_file)
            with open(limit) as limit_file:
                l = json.load(limit_file)  
                i.update(l)
                WriteToRecipe(i, RECIPE_OUTPUT)


ConvertLimit()
###MergeRecipe(LIMIT_INPUT, RECIPE_OUTPUT)