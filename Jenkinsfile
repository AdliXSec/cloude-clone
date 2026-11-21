// KosanHub (K12) - CI/CD Jenkins, Linux.
// Checkout -> Test -> Build Image -> Push Image -> Deploy -> Smoke Test
//
// Credential di Jenkins (Manage Jenkins > Credentials), TIDAK ada rahasia di file ini:
//   dockerhub-kosanhub : Username with password (username Docker Hub + access token)
//   kosanhub-env       : Secret file (isi = salinan .env produksi, lihat .env.example)

pipeline {
    agent any

    options {
        // Checkout hanya di stage 'Checkout' (di dalam node), jadi kalau gagal,
        // blok post tetap punya workspace dan tidak error "hudson.FilePath is missing".
        skipDefaultCheckout()
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    environment {
        IMAGE          = 'dockeradli/kosanhub'
        COMPOSE_FILE   = 'compose.prod.yaml'
        COMPOSE_PROJECT_NAME = 'kosanhub'
        // Tag yang dideploy = nomor build, bisa ditelusuri ke build Jenkins.
        APP_IMAGE      = "dockeradli/kosanhub:${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                script { env.FAILED_STAGE = env.STAGE_NAME }
                checkout scm
                sh 'git log -1 --oneline'
            }
        }

        // pytest dijalankan di dalam Dockerfile (stage "test"). Test gagal => build gagal
        // => pipeline berhenti dan container yang sedang jalan tidak disentuh.
        stage('Test') {
            steps {
                script { env.FAILED_STAGE = env.STAGE_NAME }
                sh 'docker build --target test -t kosanhub-test:${BUILD_NUMBER} .'
            }
        }

        // Layer stage test sudah di-cache, jadi hanya merakit stage production.
        stage('Build Image') {
            steps {
                script { env.FAILED_STAGE = env.STAGE_NAME }
                sh '''
                    docker build --target production \
                        -t "${IMAGE}:${BUILD_NUMBER}" -t "${IMAGE}:latest" .
                '''
            }
        }

        stage('Push Image') {
            steps {
                script { env.FAILED_STAGE = env.STAGE_NAME }
                withCredentials([usernamePassword(credentialsId: 'dockerhub-credentials',
                                                  usernameVariable: 'DH_USER',
                                                  passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        trap 'docker logout >/dev/null 2>&1' EXIT
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker push "${IMAGE}:${BUILD_NUMBER}"
                        docker push "${IMAGE}:latest"
                    '''
                }
            }
        }

        // Deploy dari image yang baru di-push (bukan build lokal). Volume data TIDAK dihapus.
        stage('Deploy') {
            steps {
                script { env.FAILED_STAGE = env.STAGE_NAME }
                withCredentials([file(credentialsId: 'kosanhub-env', variable: 'ENV_FILE')]) {
                    sh '''
                        DC="docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE}"
                        $DC config -q
                        $DC pull
                        $DC up -d --remove-orphans --wait --wait-timeout 180
                        $DC ps
                    '''
                }
            }
        }

        // 1) /health harus 200  2) API menerima login admin
        // 3) K12: picu job tagihan, lalu pastikan container worker menyelesaikannya.
        stage('Smoke Test') {
            steps {
                script { env.FAILED_STAGE = env.STAGE_NAME }
                withCredentials([file(credentialsId: 'kosanhub-env', variable: 'ENV_FILE')]) {
                    sh '''#!/usr/bin/env bash
                        set -eu
                        # Ambil login admin dari secret file; tidak pernah di-echo.
                        get() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }
                        ADMIN_EMAIL="$(get ADMIN_EMAIL)"; ADMIN_PASSWORD="$(get ADMIN_PASSWORD)"; PORT="$(get APP_PORT)"
                        PORT="${PORT:-8000}"
                        [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ] || { echo "ADMIN_EMAIL/ADMIN_PASSWORD kosong di kosanhub-env"; exit 1; }
                        BASE="http://localhost:${PORT}"
                        api() { curl -sS -u "${ADMIN_EMAIL}:${ADMIN_PASSWORD}" "$@"; }

                        echo "== 1. /health"
                        for i in $(seq 1 30); do
                            code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health" || true)"
                            [ "$code" = 200 ] && break
                            sleep 1
                        done
                        [ "$code" = 200 ] || { echo "/health = $code"; exit 1; }
                        echo "OK (200)"

                        echo "== 2. API + auth"
                        code="$(api -o /dev/null -w '%{http_code}' "$BASE/api/jobs")"
                        [ "$code" = 200 ] || { echo "GET /api/jobs = $code (login admin gagal?)"; exit 1; }
                        echo "OK (200)"

                        echo "== 3. Job tagihan diproses worker"
                        JOB_ID="$(api -X POST -H 'Content-Type: application/json' -d '{}' "$BASE/api/jobs/generate-bills" | jq -r '.id')"
                        echo "job id = $JOB_ID"
                        status=""
                        for i in $(seq 1 30); do
                            status="$(api "$BASE/api/jobs/${JOB_ID}" | jq -r '.status')"
                            echo "  status = $status"
                            case "$status" in COMPLETED|FAILED) break ;; esac
                            sleep 2
                        done
                        [ "$status" = COMPLETED ] || { echo "Worker tidak menyelesaikan job (status=$status)"; exit 1; }
                        echo "OK: worker memproses job"
                    '''
                }
            }
        }
    }

    // Ringkasan hasil di console log. Hanya metadata build, tidak ada rahasia yang dicetak.
    post {
        success {
            echo """
==================== RINGKASAN: SUCCESS ====================
 Job      : ${env.JOB_NAME} #${env.BUILD_NUMBER}
 Hasil    : SUCCESS (semua stage lolos, termasuk Smoke Test + worker K12)
 Image    : ${env.IMAGE}:${env.BUILD_NUMBER} (juga di-tag :latest, sudah di-push)
 Deploy   : compose project '${env.COMPOSE_PROJECT_NAME}' memakai ${env.COMPOSE_FILE}
 Durasi   : ${currentBuild.durationString.replace(' and counting', '')}
 Detail   : ${env.BUILD_URL}
============================================================"""
        }
        failure {
            echo """
==================== RINGKASAN: FAILURE ====================
 Job      : ${env.JOB_NAME} #${env.BUILD_NUMBER}
 Hasil    : FAILURE, pipeline berhenti di stage '${env.FAILED_STAGE ?: 'tidak diketahui'}'
 Image    : ${env.IMAGE}:${env.BUILD_NUMBER}
 Catatan  : bila gagal di Test/Build/Push, container yang sedang berjalan tidak disentuh
 Durasi   : ${currentBuild.durationString.replace(' and counting', '')}
 Detail   : ${env.BUILD_URL}console
============================================================"""
            withCredentials([file(credentialsId: 'kosanhub-env', variable: 'ENV_FILE')]) {
                sh 'docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} logs --tail=40 app worker || true'
            }
        }
        aborted {
            echo "RINGKASAN: ABORTED - ${env.JOB_NAME} #${env.BUILD_NUMBER} dihentikan di stage '${env.FAILED_STAGE ?: 'tidak diketahui'}'"
        }
        always {
            sh 'docker image rm kosanhub-test:${BUILD_NUMBER} || true'
        }
    }
}
