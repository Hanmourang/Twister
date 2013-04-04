/*
File: About.java ; This file is part of Twister.
Version: 2.001

Copyright (C) 2012-2013 , Luxoft

Authors: Andrei Costachi <acostachi@luxoft.com>
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

import javax.swing.JPanel;
import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.Color;
import java.awt.Graphics;
import java.awt.Font;

public class About extends JPanel{
    public About(){
        setLayout(new BorderLayout());
        JPanel p = new JPanel(){
            public void paint(Graphics g){
                //Graphics2D g2d = (Graphics2D)g;
                //g2d.setComposite(AlphaComposite.Clear);
                //g2d.fillRect(0, 0, 640, 480);
                //g2d.setComposite(AlphaComposite.SrcOver);
                //g.setColor(Color.GRAY);
                //g.fillRoundRect(10, 350, (int)(620*percent), 30, 15, 15);
                //g.setColor(Color.BLACK);
                //g.drawRoundRect(10, 350, 620, 30, 15, 15);
                //g.setFont(new Font("TimesRoman", 0, 14));
                //g.drawString(text, 30, 374);
                g.drawImage(Repository.background, 0, 0, null);
                g.setFont(new Font("TimesRoman", Font.BOLD, 14));
                g.drawString("Twister Framework", 225, 150);
                g.drawString("V.: "+Repository.getVersion(), 265, 165);
            }
        };
        p.setBackground(Color.RED);
        p.setSize(new Dimension(400,300));
        p.setPreferredSize(new Dimension(400,300));
        p.setMinimumSize(new Dimension(400,300));
        p.setMaximumSize(new Dimension(400,300));
        add(p,BorderLayout.CENTER );
    }

    
}
