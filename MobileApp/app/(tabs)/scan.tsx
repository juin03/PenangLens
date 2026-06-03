import { useState, useRef, useMemo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, Image } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { GestureDetector, Gesture, GestureHandlerRootView } from 'react-native-gesture-handler';
import { Colors, Radius, scale } from '@/constants/theme';
import { API_BASE_URL } from '@/api/client';

import { scanLandmark } from '@/api/client';

export default function ScanScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [permission, requestPermission] = useCameraPermissions();
  const [scanning, setScanning] = useState(false);
  const [flash, setFlash] = useState(false);
  const [capturedUri, setCapturedUri] = useState<string | null>(null);
  const [zoom, setZoom] = useState(0);
  const zoomRef = useRef(0);       // always up-to-date, readable from gesture callbacks
  const startZoom = useRef(0);     // zoom level captured at pinch start
  const cameraRef = useRef<CameraView>(null);

  const pinchGesture = useMemo(() => Gesture.Pinch()
    .runOnJS(true)
    .onStart(() => {
      startZoom.current = zoomRef.current;
    })
    .onUpdate((e) => {
      const next = Math.min(1, Math.max(0, startZoom.current + (e.scale - 1) * 0.4));
      zoomRef.current = next;
      setZoom(next);
    }), []);

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
      const data = await scanLandmark(uri);
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
    <GestureHandlerRootView style={styles.container}>
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
        <GestureDetector gesture={pinchGesture}>
        <CameraView ref={cameraRef} style={styles.camera} facing="back" flash={flash ? 'on' : 'off'} zoom={zoom}>
          {/* Top bar — flash only */}
          <View style={[styles.topBar, { paddingTop: insets.top + scale(10) }]}>
            <View style={{ flex: 1 }} />
            <TouchableOpacity style={styles.topBtn} onPress={() => setFlash(!flash)}>
              <View style={{ width: 24, height: 24, alignItems: 'center', justifyContent: 'center' }}>
                <View style={{ width: 2, height: 14, backgroundColor: flash ? '#fbbf24' : '#fff', borderRadius: 1 }} />
                {flash && <>
                  <View style={{ position: 'absolute', width: 14, height: 2, backgroundColor: '#fbbf24', borderRadius: 1 }} />
                  <View style={{ position: 'absolute', width: 10, height: 2, backgroundColor: '#fbbf24', borderRadius: 1, transform: [{ rotate: '45deg' }] }} />
                  <View style={{ position: 'absolute', width: 10, height: 2, backgroundColor: '#fbbf24', borderRadius: 1, transform: [{ rotate: '-45deg' }] }} />
                </>}
              </View>
            </TouchableOpacity>
          </View>

          {/* Viewfinder hint */}
          <View style={styles.hintWrap}>
            <Text style={styles.hintText}>Align a landmark and tap the shutter</Text>
          </View>

          {/* Bottom bar */}
          <View style={styles.bottomBar}>
            <TouchableOpacity style={styles.sideBtn} onPress={handlePickFromLibrary}>
              <View style={{ width: 26, height: 26, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.25)', alignItems: 'center', justifyContent: 'center' }}>
                <View style={{ width: 18, height: 18, borderRadius: 3, borderWidth: 2, borderColor: '#fff' }} />
              </View>
            </TouchableOpacity>
            <TouchableOpacity style={styles.captureBtn} onPress={handleCapture}>
              <View style={styles.captureOuter}>
                <View style={styles.captureInner} />
              </View>
            </TouchableOpacity>
            <View style={styles.sideBtn} />
          </View>
        </CameraView>
        </GestureDetector>
      )}
    </GestureHandlerRootView>
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
