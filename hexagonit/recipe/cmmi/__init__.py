import zc.buildout
import urlparse
import tempfile
import logging
import urllib
import shutil
import md5
import imp
import os

import hexagonit.recipe.download

class Recipe:
    """zc.buildout recipe for compiling and installing software"""

    def __init__(self, buildout, name, options):
        self.options = options
        self.buildout = buildout
        self.name = name

        log = logging.getLogger(self.name)

        options['location'] = os.path.join(
            buildout['buildout']['parts-directory'],
            self.name)
        options['prefix'] = options['location']
        options['url'] = options['url']

    def update(self):
        pass

    def call_script(self, script):
        """This method is copied from z3c.recipe.runscript.

        See http://pypi.python.org/pypi/z3c.recipe.runscript for details.
        """
        filename, callable = script.split(':')
        filename = os.path.abspath(filename)
        module = imp.load_source('script', filename)
        # Run the script with all options
        getattr(module, callable.strip())(self.options, self.buildout)

    def run(self, cmd):
        log = logging.getLogger(self.name)
        if os.system(cmd):
            log.error('Error executing command: %s' % cmd)
            raise zc.buildout.UserError('System error')

    def install(self):
        log = logging.getLogger(self.name)

        make_cmd = self.options.get('make-binary', 'make').strip()
        make_targets = ' '.join(self.options.get('make-targets', 'install').split())

        configure_options = ' '.join(self.options.get('configure-options','').split())

        patch_cmd = self.options.get('patch-binary', 'patch').strip()
        patch_options = ' '.join(self.options.get('patch-options', '-p0').split())
        patches = self.options.get('patches', '').split()

        compile_dir = tempfile.mkdtemp(self.name)
        
        # Download the source using hexagonit.recipe.download
        try:
            opt = self.options.copy()
            opt['destination'] = compile_dir
            hexagonit.recipe.download.Recipe(
                self.buildout, self.name, opt).install()
        except:
            shutil.rmtree(compile_dir)
            raise

        os.mkdir(self.options['location'])
        os.chdir(compile_dir)
        
        try:
            if not os.path.isfile('configure'):
                contents = os.listdir(compile_dir)
                if len(contents) == 1:
                    os.chdir(contents[0])
                    if not os.path.isfile('configure'):
                        log.error('Unable to find the configure script')
                        raise zc.buildout.UserError('Invalid package contents')
            
            if patches:
                log.info('Applying patches')
                for patch in patches:
                    self.run('%s %s < %s' % (patch_cmd, patch_options, patch))

            if 'pre-configure-hook' in self.options:
                log.info('Executing pre-configure-hook')
                self.call_script(self.options['pre-configure-hook'])

            self.run('./configure --prefix=%s %s' % (self.options['prefix'], configure_options))

            if 'pre-make-hook' in self.options:
                log.info('Executing pre-make-hook')
                self.call_script(self.options['pre-make-hook'])

            self.run(make_cmd)
            self.run('%s %s' % (make_cmd, make_targets))

            if 'post-make-hook' in self.options:
                log.info('Executing post-make-hook')
                self.call_script(self.options['post-make-hook'])

        except:
            log.error('Compilation error. The package is left as is at %s where '
                      'you can inspect what went wrong' % os.getcwd())
            raise

        if self.options.get('keep-compile-dir', '').lower() in ('true', 'yes', '1', 'on'):
            self.options['compile-dir'] = os.getcwd()
        else:
            shutil.rmtree(compile_dir)

        return [self.options['location']]