import sys
import os
import glob as gb
import re
from conans import ConanFile, AutoToolsBuildEnvironment, tools
from conans.errors import ConanException


class OpenstudiorubyConan(ConanFile):
    name = "openstudio_ruby"
    version = "2.5.5"
    license = "<Put the package license here>"
    author = "<Put your name here> <And your email here>"
    url = "https://github.com/NREL/conan-openstudio-ruby/"
    description = "A conan package to build ruby for OpenStudio."
    topics = ("openstudio", "ruby", "commercialbuildings")
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "*"
    # generators = "cmake"

    extensions = (
        "zlib",
        "openssl",
        "libyaml",
        "libffi",
        #"dbm",
        "gdbm",
        "readline",
        #"pty",
        #"syslog",
    )
    options = dict(
        {
            "shared": [True, False],
            # "fPIC": [True, False],
        },
        **{"with_" + extension: [True, False] for extension in extensions}
    )
    default_options = dict(
        {
            'shared': False,
            # 'fPIC': True,
            'with_libyaml': True,
            'with_libffi': True,
            'with_gdbm': True,
            'with_readline': True,
            'with_zlib': True,
            'with_openssl': True,
            #'with_dbm': False,
            #'with_pty': False,
            #'with_syslog': False,
        },
        # **{"with_" + extension: True for extension in extensions}
    )

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _build_subfolder(self):
        return "build_subfolder"


    def configure(self):
        if (self.settings.os == "Windows" and self.settings.compiler == "Visual Studio"):
            # raise ConanInvalidConfiguration("readline is not supported for Visual Studio")
            self.output.warn("Readline (and therefore GDBM) will not work on "
                             "MSVC right now")
            self.options.with_gdbm = False
            self.options.with_readline = False

    def requirements(self):
        """
        Declare required dependencies
        """

        # TODO: should I add termcap and ncurse, and gmp?
        if self.options.with_openssl:
            self.requires("OpenSSL/1.1.0g@conan/stable")
            self.options["OpenSSL"].shared = self.options.shared

        if self.options.with_zlib:
            self.requires("zlib/1.2.11@conan/stable")
            self.options["zlib"].shared = self.options.shared
            self.options["zlib"].minizip = True

        if self.options.with_libyaml:
            self.requires("libyaml/0.2.2@bincrafters/stable")
            self.options["libyaml"].shared = self.options.shared
            # self.options["libyaml"].fPIC = True

        if self.options.with_libffi:
            self.requires("libffi/3.2.1@bincrafters/stable")
            self.options["libffi"].shared = self.options.shared
            # self.options["libffi"].fPIC = True

        if self.options.with_gdbm:
            self.requires("gdbm/1.18.1@jmarrec/testing")
            self.options["gdbm"].shared = self.options.shared
            # self.options["gdbm"].fPIC = True
            self.options["gdbm"].libgdbm_compat = True

        if self.options.with_readline:
            self.requires("readline/7.0@bincrafters/stable")
            self.options["readline"].shared = self.options.shared
            # self.options["readline"].fPIC = True

    def build_requirements(self):
        """
        Build requirements are requirements that are only installed and used
        when the package is built from sources. If there is an existing
        pre-compiled binary, then the build requirements for this package will
        not be retrieved.
        """
        self.build_requires("ruby_installer/2.5.5@bincrafters/stable")
        self.build_requires("bison_installer/3.3.2@bincrafters/stable")
        if tools.os_info.is_windows:
            self.build_requires("msys2_installer/20161025@bincrafters/stable")
            # We need sed and bison really...

    def source(self):
        """
        Download and patch the source
        """
        # eg: https://cache.ruby-lang.org/pub/ruby/2.5/ruby-2.5.5.tar.gz
        url = "https://cache.ruby-lang.org/pub/ruby/{0}/ruby-{1}.tar.gz"
        url = url.format(self.version[:self.version.rfind('.')], self.version)
        sha256 = '28a945fdf340e6ba04fc890b98648342e3cccfd6d223a48f3810572f11b2514c'
        tools.get(url, sha256=sha256)
        extracted_dir = "ruby-" + self.version
        os.rename(extracted_dir, self._source_subfolder)

        # Same as patch -p1
        tools.patch(base_path=self._source_subfolder,
                    patch_file="Ruby.patch", strip=0)
        if self.settings.os == 'Windows':
            tools.patch(base_path=self._source_subfolder,
                        patch_file='Ruby.win.patch', strip=0)

        # The 'nodynamic' modules patch fails to build in any way on Unix,
        # with 2.5.x, so we aren't using it (at the moment anyhow)
        # tools.patch(base_path=self._source_subfolder,
        #             patch_file='Ruby.nodynamic.patch', strip=0)

    def build_configure(self):
        conf_args = [
            "--disable-install-doc"
        ]

        # if self.options.shared:
            # conf_args.append("--enable-shared")
            # conf_args.append("--disable-static")
            # conf_args.append("--disable-install-static-library")
        # else:
            # conf_args.append("--disable-shared")
            # conf_args.append("--enable-static")
            # conf_args.append("--with-static-linked-ext")

        conf_args.append("--with-static-linked-ext")

        # TODO: For windows, not sure yet if needed
        ext_libs = []
        for ext in self.extensions:
            if getattr(self.options, "with_" + ext):
                ext_name = ext
                if ext == "openssl":
                    ext_name = 'OpenSSL'
                ext_root_path = self.deps_cpp_info[ext_name].rootpath
                conf_args.append("--with-{e}-dir={r}".format(e=ext,
                                                             r=ext_root_path))

                if self.settings.compiler == "Visual Studio":

                    ext_libs_paths = self.deps_cpp_info[ext_name].lib_paths
                    if len(ext_libs_paths) != 1:
                        raise ConanException("Expected only 1 lib path for {}, "
                                             "found {}".format(ext_name,
                                                               len(ext_libs_paths)))
                    map_to_ext = {'OpenSSL': ['libcrypto.lib', 'libssl.lib'],
                                  'zlib': ['zlib.lib'],
                                  'libyaml': ['yaml.lib'],
                                  'libffi': ['libffi.lib']
                                 }
                    for libname in map_to_ext[ext_name]:
                        ext_libs.append(os.path.join(ext_libs_paths[0], libname))
            else:
                # conf_args.append("--without-{}".format(ext))
                pass

        with tools.chdir(self._source_subfolder):
            if self.settings.compiler == "Visual Studio":
                self.output.error("EXTLIBS={}".format(" ".join(ext_libs)))
                with tools.environment_append(
                    {
                        "INCLUDE": self.deps_cpp_info.include_paths,
                        "LIB": self.deps_cpp_info.lib_paths,
                        "CL": "/MP",
                        #"CFLAGS": ['-wd4996', '-we4028', '-we4142', '-Zm600',
                        #           '-Zi'],
                        "EXTLIBS": " ".join(ext_libs),
                    }):
                    if self.settings.arch == "x86":
                        target = "i686-mswin32"
                    elif self.settings.arch == "x86_64":
                        target = "x64-mswin64"
                    else:
                        raise ConanException("Invalid arch")
                    conf_args.append('--prefix="{}"'.format(self.package_folder))
                    conf_args.append("--target={}".format(target))
                    base_exe = os.path.join(
                        self.deps_cpp_info['ruby_installer'].rootpath,
                        "bin", "ruby.exe"
                    )
                    self.output.warn("Base ruby exe: {}".format(base_exe))
                    conf_args.append("--with-baseruby={}".format(base_exe))
                    # TODO: --without-win32ole ?
                    conf_args.append("--without-win32ole")
                    # TODO: adjust flags and such?
                    # set CL=/MP
                    # set CFLAGS=${CURRENT_CMAKE_C_FLAGS} -wd4996 -we4028 -we4142 -Zm600 -Zi
                    # set EXTLIBS=%LIBFFI_LIBS% %OPENSSL_LIBS% %ZLIB_LIBS% %LIBYAML_LIBS%
                    self.output.warn("conf_args = {}".format(conf_args))
                    self.run("{c} {args}".format(
                        c=os.path.join("win32", "configure.bat"),
                        args=" ".join(conf_args)))
                    try:
                        self.run("nmake /k")
                    except:
                        self.output.warn("======= COMPILE 2ND TIME ========")
                        self.run("nmake /k")
                    self.run("nmake /k install-nodoc")
            else:
                self.output.warn("conf_args = {}".format(conf_args))
                win_bash = tools.os_info.is_windows
                autotools = AutoToolsBuildEnvironment(self, win_bash=win_bash)
                # Remove our libs; Ruby doesn't like Conan's help
                autotools.libs = []

                autotools.configure(args=conf_args)
                autotools.make()
                autotools.install()

    def build(self):
        if tools.os_info.is_windows:
            msys_bin = self.deps_env_info["msys2_installer"].MSYS_BIN
            # Make sure that Ruby is first in the path order
            path = self.deps_env_info["ruby_installer"].path + [msys_bin]
            # tools.environment_append will override if value is a string and
            # prepend if a list, so we are PREPENDING to the path which is what
            # we want
            with tools.environment_append({"PATH": path,
                                           "CONAN_BASH_PATH": os.path.join(msys_bin, "bash.exe")}):
                if self.settings.compiler == "Visual Studio":
                    with tools.vcvars(self.settings):
                        self.build_configure()
                else:
                    self.build_configure()
        else:
            self.build_configure()

    def _get_libext(self):
        # We'll glob for this extension
        if self.settings.os == "Windows":
            return "lib"
        else:
            return "a"

    def package(self):
        """
        The actual creation of the package, once that it is built, is done
        here by copying artifacts from the build folder to the package folder
        """
        # self.copy("*", src="Ruby-prefix/src/Ruby-install", keep_path=True)

        # We'll glob for this extension
        libext = _get_libext(self)

        if self.settings.os == "Windows":
            self.copy("encinit.c", src="enc/", dst="include/")
        else:
            # Delete the test folders
            tools.remove("ext/-test-")

            self.copy("rbconfig.rb", src="", dst='lib/ruby/2.5.0')

        # mkdir needed?
        self.copy("*.{}".format(libext), src="ext/", dst="lib/ext")
        self.copy("*.{}".format(libext), src="enc/", dst="lib/enc")

    def _find_config_header(self):
        """
        Locate the ruby/config.h which will be in different folders depending
        on the platform

        eg:
            include/ruby-2.5.0/x64-mswin64_140
            include/ruby-2.5.0/x86_64-linux
            include/ruby-2.5.0/x86_64-darwin17
        """
        found = []

        # Glob recursive Works in python3.4 and above only...
        if sys.version_info > (3, 4):
            found = gb.glob("**/ruby/config.h", recursive=True)
        else:
            import fnmatch
            for root, dirnames, filenames in os.walk('.'):
                for filename in fnmatch.filter(filenames, 'config.h'):
                    if root.endswith('ruby'):
                        found.append(os.path.join(root, filename))

        if len(found) != 1:
            raise ConanException("Didn't find one and one only ruby/config.h")

        p = found[0]
        abspath = os.path.abspath(os.path.join(p, os.pardir, os.pardir))
        relpath = os.path.relpath(abspath, ".")
        # Add a success (in green) to ensure it did the right thing
        self.output.success("Found config.h in {}".format(relpath))
        return relpath

    def package_info(self):
        """
        Specify certain build information for consumers of the package
        Mostly we properly define libs to link against, libdirs and includedirs
        so that it can work with OpenStudio
        """
        # We'll glob for this extension
        libext = _get_libext(self)

        # Note: If you don't specify explicitly self.package_folder, "."
        # actually already resolves to it when package_info is run

        # Glob all libraries, keeping only their name (and not the path)
        glob_pattern = "**/*.{}".format(libext)
        # glob_pattern = os.path.join(self.package_folder, glob_pattern)

        # Glob recursive Works in python3.4 and above only...
        libs = []
        if sys.version_info > (3, 4):
            libs = gb.glob(glob_pattern, recursive=True)
        else:
            import fnmatch
            for root, dirnames, filenames in os.walk('.'):
                for filename in fnmatch.filter(filenames,
                                               '*.{}'.format(libext)):
                    libs.append(os.path.join(root, filename))

        if not libs:
            # Add debug info
            self.output.info("cwd: {}".format(os.path.abspath(".")))
            self.output.info("Package folder: {}".format(self.package_folder))
            self.output.error("Globbing: {}".format(glob_pattern))
            raise ConanException("Didn't find the libraries!")

        # Remove the non-static VS libs
        if self.settings.os == "Windows":
            non_stat_re = re.compile(r'x64-vcruntime[0-9]+-ruby[0-9]+\.lib')
            exclude_libs = [x for x in libs
                            if non_stat_re.search(x)]
            if not exclude_libs:
                self.output.error("Did not find any static lib to exclude, "
                                  "expected at least one on Windows")
            else:
                print("Excluding {} non-static libs: "
                      "{}".format(len(exclude_libs), exclude_libs))

                # Now we actually exclude it
                libs = list(set(libs) - set(exclude_libs))

        # Relative to package folder: no need unless explicitly setting glob
        # to package_folder above
        # libs = [os.path.relpath(p, start=self.package_folder) for p in libs]

        # Keep only the names:
        self.cpp_info.libs = [os.path.basename(x) for x in libs]

        self.output.success("Found {} libs".format(len(libs)))

        # self.cpp_info.libdirs = ['lib', 'lib/ext', 'lib/enc']
        # Equivalent automatic detection
        # list of unique folders
        libdirs = list(set([os.path.dirname(x) for x in libs]))
        # Sort it by nesting level, smaller first
        libdirs.sort(key=lambda p: len(os.path.normpath(p).split(os.sep)))
        self.cpp_info.libdirs = libdirs

        self.cpp_info.includedirs = ['include', 'include/ruby-2.5.0']
        self.cpp_info.includedirs.append(self._find_config_header())

        self.output.info("cpp_info.libs = {}".format(self.cpp_info.libs))
        self.output.info("cpp_info.includedirs = "
                         "{}".format(self.cpp_info.includedirs))
