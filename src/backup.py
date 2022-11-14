except ConnectionResetError:
                    print("274: Connection reset error")
                    # self.writer.close()
                    self.downloading = 0
                    await self.connect()
                    # await self.writer.wait_closed()
                    # break
                except Exception as e:
                    # exc_type, exc_obj, exc_tb = sys.exc_info()
                    # fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    # print(exc_type, fname, exc_tb.tb_lineno)
                    # print(self.downloading,e)
                    pass
                else:
                    if(self.allDownloaded()):
                        # print("291")
                        self.writer.close()
                        # await self.writer.wait_closed()
                        break
                    # print(f"292: {self.ip} | {self.port}")
                    if(self.downloading==1 and not self.isEngame):
                        if(self.download_start+25<time.time()):
                            #block has timed out, so request for a new one
                            self.downloading=0
                    
                    #piece would not have been found request for a new one
                    if(self.downloading==0 and self.peer_choking==0 and self.am_interested and sum(self.present_bits)>0):
                        # print(f"301: hey im here {self.ip} {self.port}")
                        pno,blo,bls,st=await self.get_piece_block(self.ip,self.port)
                        if(st==True):
                            print("306")
                            self.writer.close()
                            return
                        if(pno==None):
                            print("piece no. NONE")
                            pass
                        else:
                            if(self.present_bits[pno]==1 and not self.isEngame()):
                                self.downloading=1
                                await self.send_request_message(pno,blo,bls)
                                self.download_start=time.time()
                    else:
                        pass
            await self.pure_seeding()
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_obj)
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print("331",exc_type, fname, exc_tb.tb_lineno)
            self.writer.close()