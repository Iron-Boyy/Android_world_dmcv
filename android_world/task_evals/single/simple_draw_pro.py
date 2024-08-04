# Copyright 2024 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tasks for Simple Draw Pro app."""

import os
import random
import subprocess
from typing import Any
from android_world.env import device_constants
from android_world.env import interface
from android_world.task_evals import task_eval
from android_world.task_evals.common_validators import file_validators
from android_world.task_evals.utils import user_data_generation
from android_world.utils import file_utils


class SimpleDrawProCreateDrawing(task_eval.TaskEval):
  """Task for checking that a new drawing has been created with a specific name."""

  app_names = ("simple draw pro",)
  complexity = 1
  schema = file_validators.CreateFile.schema
  template = (
      "Create a new drawing in Simple Draw Pro. Name it {file_name}. Save it in"
      " the Pictures folder within the sdk_gphone_x86_64 storage area."
  )

  def __init__(self, params: dict[str, Any]):
    super().__init__(params)
    self.initialized = False
    self.create_file_task = file_validators.CreateFile(
        params, os.path.join(device_constants.EMULATOR_DATA, "Pictures")
    )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    self.create_file_task.initialize_task(env)

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    file_name = self.params["file_name"]
    exists = file_utils.check_file_or_folder_exists(
        file_name, self.create_file_task.data_directory, env.base_env
    )
    return 1.0 if exists else 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, str | int]:
    words = [
        "lorem",
        "ipsum",
        "dolor",
        "sit",
        "amet",
        "consectetur",
        "adipiscing",
        "elit",
    ]
    extensions = [".png", ".svg", ".jpg"]
    random_file_name = (
        "".join(random.choices(words, k=1))
        + "_"
        + user_data_generation.generate_random_file_name()
        + random.choice(extensions)
    )

    return {
        "file_name": random_file_name,
        "text": "",  # Unused.
    }

  def tear_down(self, env: interface.AsyncEnv) -> None:
    super().tear_down(env)
    self.create_file_task.tear_down(env)

class SimpleDrawProOpen(task_eval.TaskEval):
  """Task for checking that a new drawing has been created with a specific name."""

  app_names = ("simple draw pro",)
  complexity = 1
  schema = {}
  template = (
      "Open draw App"
  )

  def is_successful(self, env: interface.AsyncEnv) -> float:
      super().is_successful(env)
      adb_command = "adb shell dumpsys window windows"
      result = subprocess.run(adb_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
      # print(result)
      result = result.stdout.split('    ')

      for i in range(len(result)):
          if len(result[i]) > len("mActivityRecord") and result[i][:len("mActivityRecord")] == "mActivityRecord":
              print(result[i])
              part = result[i].split(" ")[2].split('/')
              if part[0] == "com.google.android.draw":
                  return 1
              else:
                  return 0

  @classmethod
  def generate_random_params(cls) -> dict[str, str | int]:
      return {}

  @classmethod
  def generate_random_params(cls) -> dict[str, str | int]:
    words = [
        "lorem",
        "ipsum",
        "dolor",
        "sit",
        "amet",
        "consectetur",
        "adipiscing",
        "elit",
    ]
    extensions = [".png", ".svg", ".jpg"]
    random_file_name = (
        "".join(random.choices(words, k=1))
        + "_"
        + user_data_generation.generate_random_file_name()
        + random.choice(extensions)
    )

    return {
        "file_name": random_file_name,
        "text": "",  # Unused.
    }

  def tear_down(self, env: interface.AsyncEnv) -> None:
    super().tear_down(env)
    self.create_file_task.tear_down(env)