//! Feasibility spike: pure-Rust ONNX inference for the face detector.
//! Measures RSS and inference time so we can compare with the Python build.

use std::time::Instant;

use image::imageops::FilterType;
use sysinfo::{Pid, System};
use tract_onnx::prelude::*;

fn rss_mb() -> f64 {
    let pid = Pid::from(std::process::id() as usize);
    let mut system = System::new();
    system.refresh_process(pid);
    system.process(pid).map(|p| p.memory() as f64 / 1_000_000.0).unwrap_or(0.0)
}

fn main() -> TractResult<()> {
    println!("start RSS {:.1} MB", rss_mb());

    let model_path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "../models/face_detection_yunet_2023mar.onnx".into());
    let image_path = std::env::args()
        .nth(2)
        .unwrap_or_else(|| r"C:\Users\jeremy josh\AppData\Local\Temp\opencode\yunet\lena.jpg".into());

    let model = tract_onnx::onnx()
        .model_for_path(model_path)?
        .into_optimized()?
        .into_runnable()?;
    println!("after model load RSS {:.1} MB", rss_mb());

    let source = image::open(image_path).expect("open image").to_rgb8();
    let resized = image::imageops::resize(&source, 640, 640, FilterType::Triangle);

    // YuNet expects NCHW f32 in [0,255].
    let array = tract_ndarray::Array4::from_shape_fn((1, 3, 640, 640), |(_, c, y, x)| {
        resized[(x as u32, y as u32)][c as usize] as f32
    });
    let input: Tensor = array.into();

    let started = Instant::now();
    let output = model.run(tvec!(input.into()))?;
    println!("inference {:.1} ms, output shape {:?}", started.elapsed().as_secs_f64() * 1000.0, output[0].shape());
    println!("after inference RSS {:.1} MB", rss_mb());

    Ok(())
}
