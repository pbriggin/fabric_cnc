from setuptools import setup, find_packages

setup(
    name='fabric_cnc',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'numpy',
        'ezdxf',
        'matplotlib',
    ],
    python_requires='>=3.7',
    entry_points={
        'console_scripts': [
            'fabric_cnc=fabric_cnc.__main__:main',
        ],
    },
)
