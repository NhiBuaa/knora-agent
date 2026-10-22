using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace Knora.Dev
{
    // Only application processes join this invocation's job; storage stays outside it.
    public sealed class ProcessJob : IDisposable
    {
        private IntPtr job;
        private readonly List<Process> processes = new List<Process>();

        public ProcessJob()
        {
            job = CreateJobObjectW(IntPtr.Zero, null);
            if (job == IntPtr.Zero) throw NativeError("CREATE_JOB");
            try
            {
                ExtendedLimits limits = new ExtendedLimits();
                limits.Basic.LimitFlags = 0x2000; // KILL_ON_JOB_CLOSE, without breakaway.
                if (!SetInformationJobObject(job, 9, ref limits,
                    (uint)Marshal.SizeOf(typeof(ExtendedLimits))))
                    throw NativeError("SET_JOB_LIMITS");
            }
            catch
            {
                CloseHandle(job);
                job = IntPtr.Zero;
                throw;
            }
        }

        public Process Start(string executable, string[] arguments, string directory,
            string stdout, string stderr)
        {
            if (job == IntPtr.Zero) throw new ObjectDisposedException("ProcessJob");
            string command = Quote(executable);
            foreach (string argument in arguments) command += " " + Quote(argument);
            if (Path.GetExtension(executable).Equals(".cmd", StringComparison.OrdinalIgnoreCase) ||
                Path.GetExtension(executable).Equals(".bat", StringComparison.OrdinalIgnoreCase))
            {
                executable = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),
                    "cmd.exe");
                command = Quote(executable) + " /d /s /c \"" + command + "\"";
            }

            IntPtr input = IntPtr.Zero, output = IntPtr.Zero, error = IntPtr.Zero;
            IntPtr attributes = IntPtr.Zero, inherited = IntPtr.Zero;
            bool attributesInitialized = false;
            ProcessInformation created = new ProcessInformation();
            Process process = null;
            bool resumed = false;
            try
            {
                input = OpenFile("NUL", 0x80000000, 3);
                output = OpenFile(stdout, 0x40000000, 2);
                error = OpenFile(stderr, 0x40000000, 2);
                IntPtr size = IntPtr.Zero;
                InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref size);
                attributes = Marshal.AllocHGlobal(size);
                if (!InitializeProcThreadAttributeList(attributes, 1, 0, ref size))
                    throw NativeError("INITIALIZE_HANDLE_LIST");
                attributesInitialized = true;
                inherited = Marshal.AllocHGlobal(IntPtr.Size * 3);
                Marshal.WriteIntPtr(inherited, 0, input);
                Marshal.WriteIntPtr(inherited, IntPtr.Size, output);
                Marshal.WriteIntPtr(inherited, IntPtr.Size * 2, error);
                if (!UpdateProcThreadAttribute(attributes, 0, new IntPtr(0x20002), inherited,
                    new IntPtr(IntPtr.Size * 3), IntPtr.Zero, IntPtr.Zero))
                    throw NativeError("SET_HANDLE_LIST");

                StartupInformation startup = new StartupInformation();
                startup.Basic.Size = Marshal.SizeOf(typeof(StartupInformation));
                startup.Basic.Flags = 0x100; // STARTF_USESTDHANDLES.
                startup.Basic.Input = input;
                startup.Basic.Output = output;
                startup.Basic.Error = error;
                startup.Attributes = attributes;
                // Suspended assignment prevents even fast shells from leaving unowned children.
                if (!CreateProcessW(executable, new StringBuilder(command), IntPtr.Zero,
                    IntPtr.Zero, true, 0x08080004, IntPtr.Zero, directory, ref startup, out created))
                    throw NativeError("CREATE_PROCESS");
                if (!AssignProcessToJobObject(job, created.Process))
                    throw NativeError("ASSIGN_PROCESS");
                process = Process.GetProcessById((int)created.ProcessId);
                IntPtr retainedHandle = process.Handle; // Retain identity before ResumeThread.
                if (ResumeThread(created.Thread) == UInt32.MaxValue)
                    throw NativeError("RESUME_PROCESS");
                resumed = true;
                processes.Add(process);
                return process;
            }
            finally
            {
                if (created.Process != IntPtr.Zero && !resumed)
                {
                    TerminateProcess(created.Process, 2);
                    WaitForSingleObject(created.Process, 10000);
                    if (process != null) process.Dispose();
                }
                if (created.Thread != IntPtr.Zero) CloseHandle(created.Thread);
                if (created.Process != IntPtr.Zero) CloseHandle(created.Process);
                if (attributesInitialized) DeleteProcThreadAttributeList(attributes);
                if (attributes != IntPtr.Zero) Marshal.FreeHGlobal(attributes);
                if (inherited != IntPtr.Zero) Marshal.FreeHGlobal(inherited);
                if (input != IntPtr.Zero) CloseHandle(input);
                if (output != IntPtr.Zero) CloseHandle(output);
                if (error != IntPtr.Zero) CloseHandle(error);
            }
        }

        public bool WaitForProcesses(int timeoutMilliseconds)
        {
            if (job == IntPtr.Zero) return true;
            Stopwatch watch = Stopwatch.StartNew();
            while (watch.ElapsedMilliseconds < timeoutMilliseconds)
            {
                Accounting information;
                if (!QueryInformationJobObject(job, 1, out information,
                    (uint)Marshal.SizeOf(typeof(Accounting)), IntPtr.Zero))
                    return true;
                if (information.ActiveProcesses == 0) return true;
                Thread.Sleep(25);
            }
            return false;
        }

        public void Dispose()
        {
            if (job == IntPtr.Zero) return;
            try
            {
                if (!TerminateJobObject(job, 0)) throw NativeError("TERMINATE_JOB");
                Stopwatch deadline = Stopwatch.StartNew();
                foreach (Process process in processes) process.Dispose();
                processes.Clear();
                while (true)
                {
                    Accounting information;
                    if (!QueryInformationJobObject(job, 1, out information,
                        (uint)Marshal.SizeOf(typeof(Accounting)), IntPtr.Zero))
                        throw NativeError("QUERY_JOB");
                    if (information.ActiveProcesses == 0) return;
                    if (deadline.ElapsedMilliseconds >= 10000)
                        throw new TimeoutException("DEV_CLEANUP_TIMEOUT");
                    Thread.Sleep(25);
                }
            }
            finally
            {
                CloseHandle(job);
                job = IntPtr.Zero;
                foreach (Process process in processes) process.Dispose();
                processes.Clear();
            }
        }

        private static Win32Exception NativeError(string operation)
        {
            int code = Marshal.GetLastWin32Error();
            return new Win32Exception(code, "DEV_PROCESS_JOB_FAILED:" + operation + ":" + code);
        }

        private static IntPtr OpenFile(string path, uint access, uint disposition)
        {
            SecurityAttributes security = new SecurityAttributes();
            security.Size = Marshal.SizeOf(typeof(SecurityAttributes));
            security.Inherit = true;
            IntPtr handle = CreateFileW(path, access, 3, ref security, disposition, 0x80, IntPtr.Zero);
            if (handle == new IntPtr(-1)) throw NativeError("OPEN_STANDARD_STREAM");
            return handle;
        }

        private static string Quote(string value)
        {
            StringBuilder result = new StringBuilder("\"");
            int slashes = 0;
            foreach (char character in value)
            {
                if (character == '\\') { slashes++; continue; }
                result.Append('\\', character == '"' ? slashes * 2 + 1 : slashes);
                result.Append(character);
                slashes = 0;
            }
            return result.Append('\\', slashes * 2).Append('"').ToString();
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct BasicLimits
        {
            public long ProcessTime, JobTime;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSet, MaximumWorkingSet;
            public uint ActiveProcessLimit;
            public UIntPtr Affinity;
            public uint Priority, Scheduling;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct ExtendedLimits
        {
            public BasicLimits Basic;
            public ulong ReadOperations, WriteOperations, OtherOperations;
            public ulong ReadBytes, WriteBytes, OtherBytes;
            public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct Accounting
        {
            public long UserTime, KernelTime, PeriodUserTime, PeriodKernelTime;
            public uint PageFaults, TotalProcesses, ActiveProcesses, TerminatedProcesses;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SecurityAttributes
        {
            public int Size;
            public IntPtr Descriptor;
            [MarshalAs(UnmanagedType.Bool)] public bool Inherit;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct StartupBasic
        {
            public int Size;
            public IntPtr Reserved, Desktop, Title;
            public uint X, Y, XSize, YSize, XCharacters, YCharacters, FillAttribute, Flags;
            public ushort ShowWindow, ReservedSize;
            public IntPtr ReservedBytes, Input, Output, Error;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct StartupInformation
        {
            public StartupBasic Basic;
            public IntPtr Attributes;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct ProcessInformation
        {
            public IntPtr Process, Thread;
            public uint ProcessId, ThreadId;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateJobObjectW(IntPtr security, string name);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetInformationJobObject(IntPtr job, int kind,
            ref ExtendedLimits limits, uint length);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateJobObject(IntPtr job, uint code);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool QueryInformationJobObject(IntPtr job, int kind,
            out Accounting information, uint length, IntPtr returnedLength);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateFileW(string path, uint access, uint sharing,
            ref SecurityAttributes security, uint disposition, uint flags, IntPtr template);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CreateProcessW(string executable, StringBuilder command,
            IntPtr processSecurity, IntPtr threadSecurity, bool inherit, uint flags,
            IntPtr environment, string directory, ref StartupInformation startup,
            out ProcessInformation process);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool InitializeProcThreadAttributeList(IntPtr attributes,
            int count, int flags, ref IntPtr size);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool UpdateProcThreadAttribute(IntPtr attributes, uint flags,
            IntPtr attribute, IntPtr value, IntPtr size, IntPtr previous, IntPtr returnedSize);
        [DllImport("kernel32.dll")]
        private static extern void DeleteProcThreadAttributeList(IntPtr attributes);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint ResumeThread(IntPtr thread);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateProcess(IntPtr process, uint code);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);
    }
}
