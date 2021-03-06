#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
from conans import AutoToolsBuildEnvironment, ConanFile, tools


class GiflibConan(ConanFile):
    name = "giflib"
    version = "5.1.3"
    description = 'A library and utilities for reading and writing GIF images.'
    url = "http://github.com/bincrafters/conan-giflib"
    license = "MIT"
    homepage = "http://giflib.sourceforge.net"
    exports = ["LICENSE.md"]
    exports_sources = ["unistd.h", "gif_lib.h"]
    generators = "cmake"
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = "shared=False", "fPIC=True"
    # The exported files I took them from https://github.com/bjornblissing/osg-3rdparty-cmake/tree/master/giflib
    # refactored a little

    source_subfolder = "source_subfolder"

    def configure(self):
        del self.settings.compiler.libcxx

        if self.settings.os == "Windows":
            self.options.remove("fPIC")

    def source(self):
        zip_name = "%s-%s" % (self.name, self.version)
        tools.get("http://downloads.sourceforge.net/project/giflib/%s.tar.gz" % zip_name)
        os.rename(zip_name, self.source_subfolder)

    def build(self):
        # disable util build - tools and internal libs
        tools.replace_in_file(os.path.join(self.source_subfolder, "Makefile.in"),
                              'SUBDIRS = lib util pic $(am__append_1)',
                              'SUBDIRS = lib pic $(am__append_1)')

        if tools.os_info.is_windows:
            if tools.os_info.detect_windows_subsystem() not in ("cygwin", "msys2"):
                raise Exception("This recipe needs a Windows Subsystem to be compiled. "
                                "You can specify a build_require to:"
                                " 'msys2_installer/latest@bincrafters/stable' or"
                                " 'cygwin_installer/2.9.0@bincrafters/stable' or"
                                " put in the PATH your own installation")

        if self.settings.compiler == "Visual Studio":
            self.build_visual()
        else:
            self.build_configure()

    def build_visual(self):
        # fully replace gif_lib.h for VS, with patched version
        ver_components = self.version.split(".")
        tools.replace_in_file('gif_lib.h', '@GIFLIB_MAJOR@', ver_components[0])
        tools.replace_in_file('gif_lib.h', '@GIFLIB_MINOR@', ver_components[1])
        tools.replace_in_file('gif_lib.h', '@GIFLIB_RELEASE@', ver_components[2])
        shutil.copy('gif_lib.h', os.path.join(self.source_subfolder, 'lib'))
        # add unistd.h for VS
        shutil.copy('unistd.h', os.path.join(self.source_subfolder, 'lib'))

        with tools.chdir(self.source_subfolder):
            if self.settings.arch == "x86":
                host = "i686-w64-mingw32"
            elif self.settings.arch == "x86_64":
                host = "x86_64-w64-mingw32"
            else:
                raise Exception("unsupported architecture %s" % self.settings.arch)
            if self.options.shared:
                options = '--disable-static --enable-shared'
            else:
                options = '--enable-static --disable-shared'

            cflags = ''
            if not self.options.shared:
                cflags = '-DUSE_GIF_LIB'

            prefix = tools.unix_path(os.path.abspath(self.package_folder))
            with tools.vcvars(self.settings):
                command = './configure ' \
                          '{options} ' \
                          '--host={host} ' \
                          '--prefix={prefix} ' \
                          'CC="$PWD/compile cl -nologo" ' \
                          'CFLAGS="-{runtime} {cflags}" ' \
                          'CXX="$PWD/compile cl -nologo" ' \
                          'CXXFLAGS="-{runtime} {cflags}" ' \
                          'CPPFLAGS="-I{prefix}/include" ' \
                          'LDFLAGS="-L{prefix}/lib" ' \
                          'LD="link" ' \
                          'NM="dumpbin -symbols" ' \
                          'STRIP=":" ' \
                          'AR="$PWD/ar-lib lib" ' \
                          'RANLIB=":" '.format(host=host, prefix=prefix, options=options,
                                              runtime=self.settings.compiler.runtime, cflags=cflags)
                self.run(command, win_bash=True)
                self.run('make', win_bash=True)
                self.run('make install', win_bash=True)

    def build_configure(self):
        env_build = AutoToolsBuildEnvironment(self, win_bash=self.settings.os == 'Windows')
        if self.settings.os != "Windows":
            env_build.fpic = self.options.fPIC

        prefix = os.path.abspath(self.package_folder)
        if self.settings.os == 'Windows':
            prefix = tools.unix_path(prefix)
        args = ['--prefix=%s' % prefix]
        if self.options.shared:
            args.extend(['--disable-static', '--enable-shared'])
        else:
            args.extend(['--enable-static', '--disable-shared'])

        # mingw-specific
        if self.settings.os == 'Windows':
            if self.settings.arch == "x86_64":
                args.append('--build=x86_64-w64-mingw32')
                args.append('--host=x86_64-w64-mingw32')
            if self.settings.arch == "x86":
                args.append('--build=i686-w64-mingw32')
                args.append('--host=i686-w64-mingw32')

        with tools.chdir(self.source_subfolder):
            if self.settings.os == "Macos":
                tools.replace_in_file("configure", r'-install_name \$rpath/\$soname', r'-install_name \$soname')

            self.run('chmod +x configure')
            env_build.configure(args=args)
            env_build.make()
            env_build.make(args=['install'])

    def package(self):
        self.copy(pattern="COPYING*", dst="licenses", src=self.source_subfolder, ignore_case=True, keep_path=False)

    def package_info(self):
        if self.settings.compiler == "Visual Studio":
            if self.options.shared:
                self.cpp_info.libs = ['gif.dll.lib']
                # defined only for consuming package to use dllimport
                self.cpp_info.defines.append('USE_GIF_DLL')
            else:
                self.cpp_info.libs = ['gif']
                self.cpp_info.defines.append('USE_GIF_LIB')
        else:
            self.cpp_info.libs = ['gif']
