---
layout: home
---
Talking-Buildings
--------

I'm Suhas Devmane. Talking-Buildings is an ongoing research project for Human-Building Interaction (HBI) in Natural language.This project aims to explore the ways in which buildings can communicate with their inhabitants using natural language processing.


Why blog?
---------

[You should blog even if you have no readers](http://nathanmarz.com/blog/you-should-blog-even-if-you-have-no-readers.html).

Computer Science and Engineering
----------------------------------

I'm a Haskell enthusiast. I have submitted some patches to GHC and hadrian. I have
also contributed to many open source projects, such as [ghc][16], [apache-arrow][17],
[pandas][18], [mxnet][19], [pytorch][20], [etcd-cpp-apiv3][9], and [more][22] ...

I'm working on cloud-native engineering and thinking about how to make the computational
systems efficient, observable and robust.

Interesting Gists
-------------------

+ [./pipeline-model-parallel-visualization.ipynb][25]: Visualize various pipeline model parallelism scheduling scheme in Megatron-LM.
+ [./CRTP-(de)incomplete-(de)ambiguous.cpp][24]: How could we address the incomplete type and ambiguous dependent name problem for CRTP in C++.
+ [./containers-from-scratch.rs][21]: Rust version of "Containers From Scratch" by Liz Rice, [https://www.youtube.com/watch?v=8fi7uSYlOdc][23]
+ [./$.hs][15]: A type-level `$` operator for Haskell.
+ [./list_live_objects.py][13] A utility to inspect all live objects (of specified type) in current Python execution context.
+ [./tensorboard_logging.py][14]: A logger that write scalars, images as well as histograms to tensorboard outside the context of tensorflow ops.
+ [./hemispheres.mma][3] Drawing is as easy as 1,2,3 with Mathematica.
+ [./cpp-tricks.md][2] Modern C++ is so amazing!
+ [./.vimrc][1] I use VIM to write fancy programs.
+ [./&hellip;&hellip;][4]

Projects
----------

#### ./BUAAThesis

I'm proudly a member of [BHOSC][11] and under the umbrella of this origanization I'm
co-maintaining [the LaTeX template for thesis of Beihang University][12].

#### ./etcd-cpp-apiv3

I maintain the de-facto C++ client library [etcd-cpp-apiv3][9] for [etcd][8]. The
library was first developed by nokia and open source under the BSD-3 License hasn't
been updated for years. I'm currently maintaining the library, and implemented features
like `watch`, `lease`, `lock` and enabled both token based and certificate based authentication,
I have also submitted a bunch of bug fixes as well.

After bringing the library to live again, it has received a lot of "thanks" from the
community.

#### ./libclang

The python package [libclang][10] is an unofficial release for libclang (aka. `clang.cindex`)
from the LLVM project. It includes prebuilt libclang binary to Linux, MacOS and Windows,
reducing the burden of installing libclang python package a lot, without requiring a full
installation of LLVM and clang.

#### ./GSoC

I'm proudly a participant of **[GSoC 2019][5]** this summer in the Haskell community
supervised by [Ömer Sinan Ağacan][6], aimed at making the profiling tool
**[ThreadScope][7]** suitable for processing large eventlogs.

I write **[a series of blogs](./topic/gsoc)** about the project regularly. Due to personal
reason I missed the evaluation deadline of GSoC, unfortunally.

Writings
----------

I write blogs regularly at Github Pages to record things inspire me along the
way of coding.

<ul>
  {% for post in site.posts limit:6 %}
    <li class="alink">
      <a href="{{ post.url }}" class="red-link">
        {{ post.date | date: "%Y-%m-%d" }}&emsp;{{ post.title }}
      </a>
    </li>
  {%- endfor -%}
  <li class="alink"><a href="./blog/" class="red-link">&hellip;&hellip;</a></li>
</ul>

Pageviews
-----------

[1]: https://gist.github.com/sighingnow/086ac1b32f8ea3ba84d4


## Getting Started

- [Introduction](docs/introduction.md)
- [Installation](docs/installation.md)
- [Usage](docs/usage.md)
