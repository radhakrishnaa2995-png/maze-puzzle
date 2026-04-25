import os, json, random
from pdf_builder import build_book
os.makedirs('output', exist_ok=True)
with open('config.json') as f:
    cfg=json.load(f)
for i in range(1,cfg['books']+1):
    build_book(f'output/Book_{i}.pdf', cfg['pages_per_book'], seed=i)
print('Done')
