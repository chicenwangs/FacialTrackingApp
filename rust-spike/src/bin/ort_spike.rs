//! Same spike with ONNX Runtime (optimised kernels) instead of tract.

use std::time::Instant;

use image::imageops::FilterType;
use onnxruntime::{environment::Environment, ndarray::Array4, tensor::OrtOwnedTensor};
use sysinfo::{Pid, System};

fn rss_mb() -> f64 {
    let pid = Pid::from(std::process::id() as usize);
    let mut system = System::new();
    system.refresh_process(pid);
    system.process(pid).map(|p| p.memory() as f64 / 1_000_000.0).unwrap_or(0.0)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("start RSS {:.1} MB", rss_mb());
    let env = Environment::builder().with_name("facecam-spike").build()?;
    let model = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "../models/face_detection_yunet_2023mar.onnx".into());
    let mut session = env.new_session_builder()?.with_model_from_file(&model)?;
    println!("after model load RSS {:.1} MB", rss_mb());

    let source = image::open(r"C:\Users\jeremy josh\AppData\Local\Temp\opencode\yunet\lena.jpg")?.to_rgb8();
    let resized = image::imageops::resize(&source, 640, 640, FilterType::Triangle);
    let array = Array4::from_shape_fn((1, 3, 640, 640), |(_, c, y, x)| {
        resized[(x as u32, y as u32)][c as usize] as f32
    });

    let outputs: Vec<OrtOwnedTensor<f32, _>> = session.run(vec![array.clone()])?;
    println!("output {:?}", outputs[0].shape());
    drop(outputs);
    let started = Instant::now();
    for _ in 0..20 {
        let _batch: Vec<OrtOwnedTensor<f32, _>> = session.run(vec![array.clone()])?;
    }
    println!("inference {:.1} ms avg over 20",
             started.elapsed().as_secs_f64() * 1000.0 / 20.0);
    println!("after inference RSS {:.1} MB", rss_mb());
    Ok(())
}
