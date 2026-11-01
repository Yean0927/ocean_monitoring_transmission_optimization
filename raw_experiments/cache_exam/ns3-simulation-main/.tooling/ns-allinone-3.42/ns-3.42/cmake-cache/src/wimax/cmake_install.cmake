# Install script for directory: /Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/usr/local")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "optimized")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

# Set path to fallback-tool for dependency-resolution.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/Library/Developer/CommandLineTools/usr/bin/objdump")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/build/lib/libns3.42-wimax-optimized.dylib")
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.42-wimax-optimized.dylib" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.42-wimax-optimized.dylib")
    execute_process(COMMAND /usr/bin/install_name_tool
      -delete_rpath "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/build/lib"
      -add_rpath "/usr/local/lib:$ORIGIN/:$ORIGIN/../lib:/usr/local/lib64:$ORIGIN/:$ORIGIN/../lib64"
      "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.42-wimax-optimized.dylib")
    if(CMAKE_INSTALL_DO_STRIP)
      execute_process(COMMAND "/Library/Developer/CommandLineTools/usr/bin/strip" -x "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libns3.42-wimax-optimized.dylib")
    endif()
  endif()
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/ns3" TYPE FILE FILES
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/helper/wimax-helper.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/wimax-channel.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/wimax-net-device.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/bs-net-device.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/ss-net-device.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/cid.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/cid-factory.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/ofdm-downlink-frame-prefix.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/wimax-connection.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/ss-record.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/mac-messages.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/dl-mac-messages.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/ul-mac-messages.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/wimax-phy.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/simple-ofdm-wimax-phy.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/simple-ofdm-wimax-channel.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/send-params.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/service-flow.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/ss-manager.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/connection-manager.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/wimax-mac-header.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/wimax-mac-queue.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/crc8.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/service-flow-manager.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/bs-uplink-scheduler.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/bs-uplink-scheduler-simple.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/bs-uplink-scheduler-mbqos.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/bs-uplink-scheduler-rtps.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/ul-job.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/bs-scheduler.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/bs-scheduler-simple.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/bs-scheduler-rtps.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/service-flow-record.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/snr-to-block-error-rate-record.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/snr-to-block-error-rate-manager.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/simple-ofdm-send-param.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/ss-service-flow-manager.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/bs-service-flow-manager.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/cs-parameters.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/ipcs-classifier-record.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/wimax-tlv.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/ipcs-classifier.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/bvec.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/src/wimax/model/wimax-mac-to-mac-header.h"
    "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/build/include/ns3/wimax-module.h"
    )
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
if(CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42/cmake-cache/src/wimax/install_local_manifest.txt"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
