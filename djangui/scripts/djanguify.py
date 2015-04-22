#!/usr/bin/env python
__author__ = 'chris'
description = """
Convert things to django
"""
import sys
import traceback
import os
import imp
import subprocess
import shutil
import tempfile
from itertools import chain
from argparse import ArgumentParser, FileType
from django.template import Context, Engine

from djangui.backend.nodes import ArgParseNodeBuilder
from djangui.backend.ast import source_parser


def main():
    parser = ArgumentParser(description=description)
    parser.add_argument('-s', '--scripts', help='A file or folder to look for scripts.', type=str, required=True)
    parser.add_argument('-r', '--recursive', help='Recursively search for scripts.', action='store_true')
    parser.add_argument('-a', '--app', help='The name of the app to create.', type=str, required=True)
    parser.add_argument('-p', '--project', help='The name of the django project to create.', type=str)
    parser.add_argument('--update', help='Update the model definitions of a given app.', action='store_true')
    args = parser.parse_args()
    scripts_path = args.scripts
    scripts = []
    if os.path.isdir(scripts_path):
        if args.recursive:
            for root, folders, files in os.path.walk(scripts_path):
                scripts += [os.path.join(root, filename) for filename in files if filename.endswith('.py')]
        else:
            scripts += [os.path.join(scripts_path, filename) for filename in os.listdir(scripts_path) if filename.endswith('.py')]
    else:
        scripts.append(scripts_path)

    project_name = args.project
    app_name = args.app
    app_base_dir = ''
    update_app = args.update
    if project_name:
        new_project = not os.path.exists(project_name)
        if new_project and not update_app:
            subprocess.call(['django-admin.py', 'startproject', project_name])
        project_root = os.path.join(app_base_dir, project_name)
        project_base_dir = os.path.join(project_root, project_name)
        app_base_dir = os.path.join(app_base_dir, project_name)
    app_base_dir = os.path.join(app_base_dir, app_name)

    if not update_app:
        com = ['django-admin.py', 'startapp', app_name]
        if project_name:
            app_path = os.path.join(os.path.abspath(project_name), app_name)
            if os.path.exists(app_path):
                sys.stderr.write('App {0} already exists. Did you forget the --update flag?\n'.format(app_path))
                return 1
            os.mkdir(app_path)
            com.append(app_path)
        subprocess.call(com)

    djanguify_folder = os.path.split(os.path.realpath(__file__))[0]
    app_template_dir = os.path.join(djanguify_folder, '..', 'conf', 'script_template')
    project_template_dir = os.path.join(djanguify_folder, '..', 'conf', 'project_template')

    app_models = []

    for script in scripts:
        if '__init__' in script:
            continue
        basename, extension = os.path.splitext(script)
        filename = os.path.split(basename)[1]
        try:
            module = imp.load_source(filename, script)
        except:
            sys.stderr.write('Error while loading {0}:\n'.format(script))
            sys.stderr.write('{0}\n'.format(traceback.format_exc()))
            continue
        parsers = [v for i, v in chain(module.main.__globals__.iteritems(), vars(module).iteritems())
                   if issubclass(type(v), ArgumentParser)]
        if not parsers:
            f = tempfile.NamedTemporaryFile()
            ast_source = source_parser.parse_source_file(script)
            python_code = source_parser.convert_to_python(list(ast_source))
            f.write('\n'.join(python_code))
            f.seek(0)
            module = imp.load_source(filename, f.name)
            parsers = [v for i, v in chain(module.main.__globals__.iteritems(), vars(module).iteritems())
                   if issubclass(type(v), ArgumentParser)]
        if not parsers:
            sys.stderr.write('Unable to identify ArgParser for {0}:\n'.format(script))
            continue
        module_parser = parsers[0]
        parser = ArgParseNodeBuilder(filename, module_parser, script)
        app_models.append(parser.getModelDict())

    context = Context(
        dict({
            'app_name': app_name,
            'project_name': project_name,
        },
        **{
            'models': app_models,
        }),
        autoescape=False
    )

    template_files = []
    def walk_dir(templates, dest, filter=None):
        l = []
        for root, folders, files in os.walk(templates):
            for filename in files:
                if filename.endswith('.pyc') or (filter and filename not in filter):
                    continue
                relative_dir = '.{0}'.format(os.path.split(os.path.join(root, filename).replace(templates, ''))[0])
                l.append((os.path.join(root, filename), os.path.join(dest, relative_dir)))
        return l

    template_files += walk_dir(app_template_dir, app_base_dir, filter={'djangui_models.py'} if update_app else None)

    if project_name and not update_app and new_project:
        template_files += walk_dir(project_template_dir, project_base_dir)

    # remove files of directories we are overriding
    if not update_app:
        os.remove(os.path.join(app_base_dir, 'models.py'))

    for template_file, dest_dir in template_files:
        template_file = open(template_file)
        content = template_file.read()
        content = content.decode('utf-8')
        template = Engine().from_string(content)
        content = template.render(context)
        content = content.encode('utf-8')
        # import pdb; pdb.set_trace();
        to_name = os.path.join(dest_dir, os.path.split(template_file.name)[1])
        # print template_file, dest_dir, to_name
        try:
            os.mkdir(dest_dir)
        except:
            pass
        with open(to_name, 'wb') as new_file:
            new_file.write(content)

    if not update_app and new_project:
        # move the django settings to the settings path so we don't have to chase Django changes.
        shutil.move(os.path.join(project_base_dir, 'settings.py'), os.path.join(project_base_dir, 'settings', 'django_settings.py'))
        # do the same with urls
        shutil.move(os.path.join(project_base_dir, 'urls.py'), os.path.join(project_base_dir, 'urls', 'django_urls.py'))

    if project_name:
        subprocess.call(['python', os.path.join(project_root, 'manage.py'), 'makemigrations'])
        subprocess.call(['python', os.path.join(project_root, 'manage.py'), 'migrate'])
        subprocess.call(['python', os.path.join(project_root, 'manage.py'), 'collectstatic', '--noinput'])
        subprocess.call(['python', os.path.join(project_root, 'manage.py'), 'runserver'])

if __name__ == "__main__":
    sys.exit(main())