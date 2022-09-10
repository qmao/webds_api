/usr/local/bin/pyarmor obfuscate -r --bootstrap 2 --restrict=0 --platform linux.armv7 goalkeeper.py
cp dist/goalkeeper.py ../../webds_api/obfuscate/goalkeeper.py
cp dist/pytransform/__init__.py ../../webds_api/obfuscate/pytransform/pytransform.py
