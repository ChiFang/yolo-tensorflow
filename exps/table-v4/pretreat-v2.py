# -*- coding: utf-8 -*-
# author: ronniecao
import json
import os
import shutil
import random
import math
import numpy
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from scipy import misc
import platform
import logging

if 'Windows' in platform.platform():
	logging.basicConfig(
		level=logging.INFO,
		filename='E:\\Temporal\Python\darknet-master\log\pretreat.txt',
		filemode='w')
elif 'Linux' in platform.platform():
	logging.basicConfig(
		level=logging.INFO,
		filename='/home/ronniecao/yolo/darknet/log/pretreat.txt',
		filemode='a+')

colors = {
	'word': [150, 150, 150], # 灰色
	'date': [30, 144, 255], # 蓝色
	'digit': [67, 205, 128], # 绿色
	'line': [54, 54, 54], # 黑色
	'page': [159, 121, 238], # 紫色
	'table': [255, 99, 71], # 红色
	'picture': [255, 236, 139], # 黄色
	'cell': [255, 222, 173], #橙色
} 

def load_table_json(maindir):
	contents_dict = {}
	dirlist = os.listdir(os.path.join(maindir))
	for idx, docid in enumerate(dirlist):
		# docid = '169'
		if docid == 'errors':
			continue
		contents_dict[docid] = {}
		with open(os.path.join(maindir, docid, 'pages_with_tables'), 'r') as fo:
			data = json.load(fo)
			n_processed = 0
			for pageid in data:
				n_processed += 1
				logging.info('Read Json Files: doc: %s, doc rate: %.2f%%, page: %s, page rate: %.2f%%' % (
					docid, 100.0 * (idx+1) / len(dirlist), 
					pageid, 100.0 * (n_processed) / len(data)))
				contents_dict[docid][pageid] = []
				size = data[pageid]['size']
				texts, curves, others, tables = [], [], [], []
				# 获取表格框
				pad = 2
				for box in data[pageid]['tables']:
					pos = [int(math.floor(float(box[0])) - pad), \
						int(math.ceil(float(box[2])) + pad), \
						int(math.floor(float(size[1]-box[3])) - pad), \
						int(math.ceil(float(size[1]-box[1])) + pad)]
					tables.append({'position': pos, 'lines': [], 'texts': [], 'cells': []})
				# 获取文本框
				for text in data[pageid]['texts']:
					# 获取每一个字符的位置
					chars = []
					for char in text['chars']:
						pos = [int(math.floor(float(char['box'][0]))),
							int(math.floor(float(char['box'][2]))),
							int(math.floor(float(size[1]-char['box'][3]))),
							int(math.floor(float(size[1]-char['box'][1])))]
						chars.append({'position': pos, 'sentence': char['text'].strip()})
					# 对于距离近的字符进行合并
					for char in chars:
						merged = False
						for i in range(len(texts)):
							box = texts[i]
							if char['position'][2] == texts[i]['position'][2] and \
								char['position'][3] == texts[i]['position'][3] and \
								text['type'] == texts[i]['type']:
								if abs(char['position'][0] - texts[i]['position'][1]) <= 5:
									texts[i]['position'][1] = char['position'][1]
									merged = True
									break
								elif abs(char['position'][1] - texts[i]['position'][0]) <= 5:
									texts[i]['position'][0] = char['position'][0]
									merged = True
									break
						if not merged:
							texts.append({'position': char['position'], 'type': text['type'],
										'sentence': text['text'].strip()})
				new_texts = []
				for text in texts:
					for table in tables:
						if text['position'][0] >= table['position'][0] and \
							text['position'][1] <= table['position'][1] and \
							text['position'][2] >= table['position'][2] and \
							text['position'][3] <= table['position'][3]:
							table['texts'].append(text)
							break
					else:
						new_texts.append(text)
				texts = new_texts
				# 对于页码进行特殊识别
				left_bottom, middle_bottom, right_bottom = [], [], []
				for i in range(len(texts)):
					xrate = float((texts[i]['position'][0]+texts[i]['position'][1]) / 2) / size[0]
					yrate = float((texts[i]['position'][2]+texts[i]['position'][3]) / 2) / size[1]
					if 0.02 <= xrate <= 0.1 and 0.85 <= yrate <= 1.0 and \
						texts[i]['type'] == 4:
						left_bottom.append(i)
					elif 0.45 <= xrate <= 0.55 and 0.85 <= yrate <= 1.0 and \
						texts[i]['type'] == 4:
						middle_bottom.append(i)
					elif 0.90 <= xrate <= 0.94 and 0.85 <= yrate <= 1.0 and \
						texts[i]['type'] == 4:
						right_bottom.append(i)
				if len(left_bottom) != 0:
					i = max(left_bottom, key=lambda x: texts[x]['position'][3])
					texts[i]['type'] = 5
				elif len(right_bottom) != 0:
					i = max(right_bottom, key=lambda x: texts[x]['position'][3])
					texts[i]['type'] = 5
				elif len(middle_bottom) != 0:
					i = max(middle_bottom, key=lambda x: texts[x]['position'][3])
					texts[i]['type'] = 5
				# 将下划线文本框改为表格框
				new_texts = []
				for text in texts:
					isline = True
					if 'sentence' in text and text['type'] == 2:
						for s in text['sentence']:
							if s != '_':
								isline = False
						if isline and len(text['sentence']) >= 3:
							pos = [text['position'][0], text['position'][1], 
								text['position'][3]-1, text['position'][3]]
							curves.append({'position': pos, 'type': 1})
						else:
							new_texts.append(text)
					else:
						new_texts.append(text)
				texts = new_texts
				# 获取其他框（图片等）
				for other in data[pageid]['others']:
					pos = [int(math.floor(float(other['box'][0]))), \
						int(math.floor(float(other['box'][2]))), \
						int(math.floor(float(size[1]-other['box'][3]))), \
						int(math.floor(float(size[1]-other['box'][1])))]
					others.append({'position': pos, 'type': other['type']})
				# 获取每一个线条的位置
				curves = []
				curve_width = 2
				for curve in data[pageid]['curves']:
					pos = [int(math.floor(float(curve['box'][0]))), \
						int(math.floor(float(curve['box'][2]))), \
						int(math.floor(float(size[1]-curve['box'][3]))), \
						int(math.floor(float(size[1]-curve['box'][1])))]
					if pos[1] - pos[0] <= curve_width and pos[3] - pos[2] > curve_width:
						pos[1] = pos[0]
						line = {'position': pos, 'type': curve['type']}
					elif pos[1] - pos[0] > curve_width and pos[3] - pos[2] <= curve_width:
						pos[3] = pos[2]
						line = {'position': pos, 'type': curve['type']}
					for table in tables:
						if line['position'][0] >= table['position'][0] and \
							line['position'][1] <= table['position'][1] and \
							line['position'][2] >= table['position'][2] and \
							line['position'][3] <= table['position'][3] and \
							line['type'] == 1:
							table['curves'].append(line)
							break
					else:
						curves.append(line)
						
				contents_dict[docid][pageid] = {
					'texts': texts, 'size': size, 'tables': tables,
					'others': others, 'curves': curves}
	
	return contents_dict

def write_json(contents_dict, path):
	with open(path, 'w') as fw:
		if 'Windows' in platform.platform():
			fw.write(json.dumps(contents_dict, indent=4))
		elif 'Linux' in platform.platform():
			fw.write(json.dumps(contents_dict))

if 'Windows' in platform.platform():
	contents_dict = load_table_json('E:\\Temporal\Python\darknet-master\datasets\\table-png\JPEGImages')
	write_json(contents_dict, 'E:\\Temporal\Python\darknet-master\datasets\\table-png\\texts.json')
elif 'Linux' in platform.platform():
	contents_dict = load_table_json('/home/wangxu/data/pdf2jpg_v4/output/')
	write_json(contents_dict, '/home/caory/github/table-detection/datasets/table-v2/texts.json')
