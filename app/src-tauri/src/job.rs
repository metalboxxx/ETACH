//! A Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (plan step 14, R14.2).
//!
//! The shell creates one at start and assigns both children to it right after spawning them.
//! When the shell exits, even by a crash, Windows closes the job's last handle and kills every
//! process in it (their own children too, which inherit the job).

#[cfg(windows)]
mod imp {
    use std::ffi::c_void;
    use std::os::windows::io::AsRawHandle;
    use std::process::Child;

    use windows_sys::Win32::Foundation::{CloseHandle, HANDLE};
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        QueryInformationJobObject, SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };

    /// An owned job handle; dropping it closes the handle (and so kills the job's processes).
    #[derive(Debug)]
    pub struct Job {
        handle: HANDLE,
    }

    // The handle is a kernel object handle; using it from another thread is fine.
    unsafe impl Send for Job {}
    unsafe impl Sync for Job {}

    impl Job {
        /// Create an unnamed job that kills its processes when its last handle closes.
        pub fn new_kill_on_close() -> std::io::Result<Self> {
            // SAFETY: plain Win32 calls with valid pointers; the handle is checked.
            unsafe {
                let handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
                if handle.is_null() {
                    return Err(std::io::Error::last_os_error());
                }
                let job = Job { handle };
                let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                let ok = SetInformationJobObject(
                    job.handle,
                    JobObjectExtendedLimitInformation,
                    &info as *const _ as *const c_void,
                    std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
                );
                if ok == 0 {
                    return Err(std::io::Error::last_os_error());
                }
                Ok(job)
            }
        }

        /// Put a child process into the job.
        pub fn assign(&self, child: &Child) -> std::io::Result<()> {
            // SAFETY: both handles are valid for the duration of the call.
            let ok = unsafe { AssignProcessToJobObject(self.handle, child.as_raw_handle() as HANDLE) };
            if ok == 0 {
                return Err(std::io::Error::last_os_error());
            }
            Ok(())
        }

        /// The job's limit flags (`JOBOBJECT_BASIC_LIMIT_INFORMATION.LimitFlags`).
        pub fn limit_flags(&self) -> std::io::Result<u32> {
            // SAFETY: the buffer is the size we pass.
            unsafe {
                let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
                let ok = QueryInformationJobObject(
                    self.handle,
                    JobObjectExtendedLimitInformation,
                    &mut info as *mut _ as *mut c_void,
                    std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
                    std::ptr::null_mut(),
                );
                if ok == 0 {
                    return Err(std::io::Error::last_os_error());
                }
                Ok(info.BasicLimitInformation.LimitFlags)
            }
        }
    }

    impl Drop for Job {
        fn drop(&mut self) {
            // SAFETY: we own the handle and close it once.
            unsafe {
                CloseHandle(self.handle);
            }
        }
    }

    pub const KILL_ON_JOB_CLOSE: u32 = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
}

#[cfg(windows)]
pub use imp::{Job, KILL_ON_JOB_CLOSE};

#[cfg(all(test, windows))]
mod tests {
    use super::*;
    use std::process::{Command, Stdio};
    use std::time::{Duration, Instant};

    /// R14.2: a child assigned to the job has `KILL_ON_JOB_CLOSE`, and closing the job kills it.
    #[test]
    fn closing_the_job_kills_its_children() {
        let job = Job::new_kill_on_close().unwrap();
        assert_ne!(job.limit_flags().unwrap() & KILL_ON_JOB_CLOSE, 0);

        let mut child = Command::new("ping")
            .args(["-n", "120", "127.0.0.1"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .unwrap();
        job.assign(&child).unwrap();
        assert!(child.try_wait().unwrap().is_none(), "the child should still run");

        drop(job);
        let deadline = Instant::now() + Duration::from_secs(5);
        loop {
            if child.try_wait().unwrap().is_some() {
                break;
            }
            if Instant::now() > deadline {
                let _ = child.kill();
                panic!("the child outlived its job");
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }
}
