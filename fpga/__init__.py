# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import platformdirs as pfd
from ._processor import Processor as Processor

platform_dir = pfd.PlatformDirs(appname="neuro_fpga", appauthor=False, roaming=False)
build_path = platform_dir.user_cache_path
networks_build_path = platform_dir.user_cache_path / "networks"
sims_build_path = platform_dir.user_cache_path / "sims"
eda_build_path = platform_dir.user_cache_path / "eda"
