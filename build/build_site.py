import io, os
BUILD = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(BUILD)
tpl = io.open(os.path.join(BUILD, 'template.html'), encoding='utf-8').read()
payload = io.open(os.path.join(BUILD, 'payload.json'), encoding='utf-8').read()
out = tpl.replace('/*__PAYLOAD__*/null', payload)
io.open(os.path.join(SITE, 'index.html'), 'w', encoding='utf-8').write(out)
print('index.html записан, размер', len(out), 'байт')
