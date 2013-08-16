%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
#
# spec file for package salt-testing
#
# Copyright (c) 2013 SUSE LINUX Products GmbH, Nuernberg, Germany.
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via http://bugs.opensuse.org/
#
Name:           salt-testing
Version:        0.5.0
Release:        1%{?dist}
License:        Apache-2.0
Summary:        Testing tools needed in the several Salt Stack projects
Url:            http://saltstack.org/
Group:          Development/Libraries/Python
Source0:        http://pypi.python.org/packages/source/s/SaltTesting/SaltTesting-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-build

%if %{?suse_version: %{suse_version} > 1110} %{!?suse_version:1}
BuildArchitectures: noarch
%endif

BuildRequires:  fdupes
BuildRequires:  python-devel
BuildRequires:  python-unittest2
Requires:		python-unittest2

%description
Required testing tools needed in the several Salt Stack projects.

%prep
%setup -q -n SaltTesting-%{version}

%build
python setup.py build

%install
python setup.py install --prefix=%{_prefix} --root=%{buildroot}
%fdupes %{buildroot}%{_prefix}

%files
%defattr(-,root,root)
%{python_sitelib}/*


%changelog
