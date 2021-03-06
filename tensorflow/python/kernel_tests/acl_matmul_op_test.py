# Copyright 2015 The TensorFlow Authors. All Rights Reserved.
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
# ==============================================================================
"""Tests for tensorflow.ops.math_ops.acl_matmul."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import operator
import numpy as np

from tensorflow.python.framework import constant_op
from tensorflow.python.framework import ops
from tensorflow.python.framework import test_util
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import gradient_checker
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import random_ops
from tensorflow.python.ops import variables
from tensorflow.python.platform import test as test_lib

# TODO(yangzihao): Currently matmul autotuning is disabled by default. Use
# os.environ["TF_MATMUL_AUTOTUNE_ENABLE"] = "1" to enable it.


def _AddTest(test, op_name, testcase_name, fn):
  test_name = "_".join(["test", op_name, testcase_name])
  if hasattr(test, test_name):
    raise RuntimeError("Test %s defined more than once" % test_name)
  setattr(test, test_name, fn)


def _GetTransposedMatrices(x, x_name, kwargs):
  if kwargs["transpose_" + x_name] is True:
    return x.T
  elif kwargs["adjoint_" + x_name] is True:
    return np.conj(x.T)
  else:
    return x


class MatMulTest(test_lib.TestCase):
  pass  # Filled in below


def _GetMatMulTest(a_np_, b_np_, use_static_shape_, **kwargs_):

  def Test(self):
    np_val = np.matrix(a_np_) * np.matrix(b_np_)
    use_gpu = True
    if a_np_.dtype is np.float16 and (
        not test_util.CudaSupportsHalfMatMulAndConv()):
      use_gpu = False
      print("Built without fp16 matmul support for Cuda, running test on CPU.")

    # Transpose and possibly conjugate a_np_ and b_np_ according to the
    # attributes such that tf.matmul(effective_a_np, effective_b_np, **kwargs)
    # results in a valid matrix multiplication and produces the same result as
    # np.matrix(a_np_) * np.matrix(b_np_)
    effective_a_np = _GetTransposedMatrices(a_np_, "a", kwargs_)
    effective_b_np = _GetTransposedMatrices(b_np_, "b", kwargs_)
    with self.test_session(use_gpu=use_gpu) as sess:
      if use_static_shape_:
        a = constant_op.constant(effective_a_np)
        b = constant_op.constant(effective_b_np)
        res = math_ops.acl_matmul(a, b, **kwargs_)
        tf_val = res.eval()
      else:
        a = array_ops.placeholder(a_np_.dtype)
        b = array_ops.placeholder(b_np_.dtype)
        res = math_ops.acl_matmul(a, b, **kwargs_)
        tf_val = sess.run(res, feed_dict={a: effective_a_np, b: effective_b_np})

    self.assertAllCloseAccordingToType(
        tf_val,
        np_val,
        float_rtol=2e-5,
        float_atol=2e-5,
        half_rtol=0.2,
        half_atol=0.2)

  return Test

if __name__ == "__main__":
  sizes = [1, 3, 5]
  trans_options = [[False, False], [False, True]]
  for use_static_shape in [False, True]:
    #for dtype in (np.float32, np.int32):
    dtype = np.float32
    if not use_static_shape and dtype == np.int32:
      # TODO(rmlarsen): Re-enable this test when we have fixed the underlying
      # bug in Windows (b/35935459).
      continue
    for m in sizes:
      for n in sizes:
        for k in sizes:
          if k == 1 or m == 1 or n == 1:
            continue;
          # Construct compatible random matrices a_np of size [m, k] and b_np
          # of size [k, n].
          a_np = np.random.normal(-5, 5, m * k).astype(dtype).reshape([m, k])
          if dtype in (np.complex64, np.complex128):
            a_np.imag = np.random.normal(-5, 5,
                                          m * k).astype(dtype).reshape([m, k])
          b_np = np.random.normal(-5, 5, k * n).astype(dtype).reshape([k, n])
          if dtype in (np.complex64, np.complex128):
            b_np.imag = np.random.normal(-5, 5,
                                          k * n).astype(dtype).reshape([k, n])
          for adjoint_a, transpose_a in trans_options:
            if transpose_a == True:
              continue;
            for adjoint_b, transpose_b in trans_options:
              name = "%s_%s_%s_%s_%s_%s_%s_%s_%s" % (
                  use_static_shape, dtype.__name__, m, n, k, adjoint_a,
                  transpose_a, adjoint_b, transpose_b)
              _AddTest(MatMulTest, "MatMulTest", name,
                        _GetMatMulTest(
                            a_np,
                            b_np,
                            use_static_shape,
                            adjoint_a=adjoint_a,
                            transpose_a=transpose_a,
                            adjoint_b=adjoint_b,
                            transpose_b=transpose_b))

  test_lib.main()
