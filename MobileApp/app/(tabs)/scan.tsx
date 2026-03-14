import { useState, useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, Image } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, scale } from '@/constants/theme';
import { API_BASE_URL } from '@/api/client';

export default function ScanScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [permission, requestPermission] = useCameraPermissions();
  const [scanning, setScanning] = useState(false);
  const [flash, setFlash] = useState(false);
  const [capturedUri, setCapturedUri] = useState<string | null>(null);
  const cameraRef = useRef<CameraView>(null);

  if (!permission) {
    return <View style={styles.center}><ActivityIndicator size="large" color={Colors.accent} /></View>;
  }

  if (!permission.granted) {
    return (
      <View style={styles.center}>
        <Text style={styles.permText}>Camera access is required to scan landmarks.</Text>
        <TouchableOpacity style={styles.permBtn} onPress={requestPermission}>
          <Text style={styles.permBtnText}>Grant Permission</Text>
        </TouchableOpacity>
      </View>
    );
  }

  /** Shared pipeline: send a local image URI to VisionML and navigate to result */
  const runScan = async (uri: string) => {
    setCapturedUri(uri);
    setScanning(true);
    try {
      const formData = new FormData();
      formData.append('image', { uri, type: 'image/jpeg', name: 'scan.jpg' } as any);
      const res = await fetch(`${API_BASE_URL}/scan`, {
        method: 'POST', body: formData,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const data = await res.json();
      if (data.success) {
        router.push({ pathname: '/landmark/result', params: { data: JSON.stringify(data) } });
      } else {
        alert('No landmarks detected. Try pointing at a Penang landmark!');
      }
    } catch (err) {
      console.error('Scan error:', err);
      alert('Scan failed. Make sure VisionML service is running on :8001.');
    } finally {
      setScanning(false);
      setCapturedUri(null);
    }
  };

  const handleCapture = async () => {
    if (!cameraRef.current || scanning) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.5 });
      if (!photo) throw new Error('Failed to take photo');
      await runScan(photo.uri);
    } catch (err) {
      console.error('Capture error:', err);
      alert('Could not capture photo.');
    }
  };

  const handlePickFromLibrary = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.6,
      allowsEditing: false,
    });
    if (result.canceled || !result.assets?.length) return;
    await runScan(result.assets[0].uri);
  };

  const handleRetake = () => {
    setCapturedUri(null);
    setScanning(false);
  };

  return (
    <View style={styles.container}>
      {/* Show captured image OR live camera */}
      {capturedUri ? (
        <View style={styles.camera}>
          <Image source={{ uri: capturedUri }} style={StyleSheet.absoluteFillObject} resizeMode="cover" />

          {/* Processing overlay */}
          <View style={styles.scanOverlay}>
            <View style={styles.scanPulse}>
              <ActivityIndicator size="large" color={Colors.accent} />
            </View>
            <Text style={styles.scanText}>Detecting landmark...</Text>
            <Text style={styles.scanSub}>DINOv2 → YOLO11 Pipeline</Text>
            <TouchableOpacity style={styles.cancelBtn} onPress={handleRetake}>
              <Text style={styles.cancelText}>Retake</Text>
            </TouchableOpacity>
          </View>
        </View>
      ) : (
        <CameraView ref={cameraRef} style={styles.camera} facing="back" flash={flash ? 'on' : 'off'}>
          {/* Top bar */}
          <View style={[styles.topBar, { paddingTop: insets.top + scale(10) }]}>
            <TouchableOpacity style={styles.topBtn}><Text style={styles.topIcon}>📍</Text></TouchableOpacity>
            <View style={{ flex: 1 }} />
            <TouchableOpacity style={styles.topBtn} onPress={() => setFlash(!flash)}>
              <Text style={styles.topIcon}>{flash ? '⚡' : '💡'}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.topBtn}><Text style={styles.topIcon}>⚙️</Text></TouchableOpacity>
          </View>

          {/* Viewfinder hint */}
          <View style={styles.hintWrap}>
            <Text style={styles.hintText}>Align a landmark and tap the shutter</Text>
          </View>

          {/* Bottom bar */}
          <View style={styles.bottomBar}>
            <TouchableOpacity style={styles.sideBtn} onPress={handlePickFromLibrary}><Text style={styles.sideIcon}>🖼️</Text></TouchableOpacity>
            <TouchableOpacity style={styles.captureBtn} onPress={handleCapture}>
              <View style={styles.captureOuter}>
                <View style={styles.captureInner} />
              </View>
            </TouchableOpacity>
            <TouchableOpacity style={styles.sideBtn}><Text style={styles.sideIcon}>🔄</Text></TouchableOpacity>
          </View>
        </CameraView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'black' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.primary, padding: scale(20) },
  permText: { color: Colors.white, fontSize: scale(14), textAlign: 'center', marginBottom: scale(14) },
  permBtn: { backgroundColor: Colors.accent, borderRadius: Radius.full, paddingVertical: scale(10), paddingHorizontal: scale(20) },
  permBtnText: { color: Colors.white, fontWeight: '700', fontSize: scale(13) },
  camera: { flex: 1 },
  topBar: { flexDirection: 'row', paddingHorizontal: scale(16), gap: scale(10) },
  topBtn: { width: scale(36), height: scale(36), borderRadius: scale(18), backgroundColor: 'rgba(0,0,0,0.3)', justifyContent: 'center', alignItems: 'center' },
  topIcon: { fontSize: scale(18) },
  hintWrap: { position: 'absolute', bottom: scale(120), alignSelf: 'center' },
  hintText: { color: 'rgba(255,255,255,0.7)', fontSize: scale(12), fontWeight: '500' },
  scanOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', alignItems: 'center',
  },
  scanPulse: { marginBottom: scale(16) },
  scanText: { color: Colors.white, fontSize: scale(16), fontWeight: '600' },
  scanSub: { color: 'rgba(255,255,255,0.5)', fontSize: scale(11), marginTop: scale(4) },
  cancelBtn: { backgroundColor: Colors.error, borderRadius: Radius.full, paddingVertical: scale(8), paddingHorizontal: scale(20), marginTop: scale(20) },
  cancelText: { color: Colors.white, fontWeight: '700', fontSize: scale(13) },
  bottomBar: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    height: scale(100), flexDirection: 'row', justifyContent: 'space-around',
    alignItems: 'center', backgroundColor: 'rgba(0,0,0,0.3)',
  },
  sideBtn: { width: scale(44), height: scale(44), borderRadius: scale(22), backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center' },
  sideIcon: { fontSize: scale(20) },
  captureBtn: { justifyContent: 'center', alignItems: 'center' },
  captureOuter: {
    width: scale(64), height: scale(64), borderRadius: scale(32),
    borderWidth: 3, borderColor: Colors.white, justifyContent: 'center', alignItems: 'center',
  },
  captureInner: { width: scale(52), height: scale(52), borderRadius: scale(26), backgroundColor: Colors.white },
});
