from setuptools import setup, find_packages
import os

version = '0.0.1'

setup(
    name='rigpl_erpnext',
    version=version,
    description='Rohit ERPNext Extensions',
    author='Rohit Industries Group Pvt. Ltd.',
    author_email='aditya@rigpl.com',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=("frappe",),
)
