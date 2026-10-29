from pathlib import Path
import subprocess,shlex,shutil,json,hashlib,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
NS3=ROOT/'cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'
# Resolve project root independently of invocation directory.
NS3=Path('/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42')
EXP=Path('/Users/yean/program/海洋监测/system-ablation-20260928-table-rates')
CACHE=NS3/'cmake-cache'
TAG=sys.argv[1] if len(sys.argv)>1 else ''
SRC=HERE/('quic-'+TAG if TAG else 'quic')
LIB=HERE/('lib-'+TAG if TAG else 'lib')
if not SRC.exists(): shutil.copytree(NS3/'contrib/quic',SRC)
LIB.mkdir(exist_ok=True)
CXX='/Library/Developer/CommandLineTools/usr/bin/c++'
def compile(src,obj,pic=False):
 cmd=[CXX,'-std=c++20','-arch','arm64','-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','-fPIC' if pic else '-fPIE','-DNS3_BUILD_PROFILE_RELEASE','-DHAVE_LIBXML2','-DHAVE_SQLITE3','-D__APPLE__','-I'+str(NS3/'build/include'),'-I/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk/usr/include/libxml2','-c',str(src),'-o',str(obj)]
 subprocess.run(cmd,check=True)
def build():
 replacements={}
 for name in ('quic-socket-base.cc','quic-stream-base.cc','quic-socket-tx-buffer.cc'):
  obj=LIB/(name+'.o');compile(SRC/'model'/name,obj,True)
  replacements['CMakeFiles/libquic-obj.dir/model/'+name+'.o']=str(obj)
 args=shlex.split((CACHE/'contrib/quic/CMakeFiles/libquic.dir/link.txt').read_text())
 args=[replacements.get(a,str(CACHE/'contrib/quic'/a) if a.startswith('CMakeFiles/') else a) for a in args]
 args[args.index('-o')+1]=str(LIB/'libns3.42-quic-optimized.dylib')
 subprocess.run(args,check=True)
 if TAG:return
 compile(HERE/'system-ablation-diag.cc',HERE/'application.o')
 args=shlex.split((CACHE/'scratch/CMakeFiles/scratch_system-ablation.dir/link.txt').read_text())
 args=[str(HERE/'application.o') if a=='CMakeFiles/scratch_system-ablation.dir/system-ablation.cc.o' else a for a in args]
 args[args.index('-o')+1]=str(HERE/'system-ablation-diag')
 args.insert(1,'-Wl,-rpath,'+str(HERE/'lib'))
 subprocess.run(args,check=True)
 print('Built isolated diagnostic executable',flush=True)
if __name__=='__main__':build()
